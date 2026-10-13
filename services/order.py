from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.item import Item
from db.models.order import Order, OrderPhone
from db.models.user import User
from services import wallet as wallet_svc


def _make_order_code(order_id: int) -> str:
    return f"#{order_id:06d}"


async def create_order(
    session: AsyncSession,
    user: User,
    item: Item,
    qty: int,
    phones: list[str],
    unit_price: Decimal,
) -> Order:
    total = unit_price * qty

    order = Order(
        order_code="",
        user_id=user.id,
        role_at_order=user.role,
        tier_at_order=user.tier_id,
        item_id=item.id,
        item_name=item.name,
        qty=qty,
        unit_price=unit_price,
        total=total,
        status="pending",
    )
    session.add(order)
    await session.flush()

    order.order_code = _make_order_code(order.id)

    for phone in phones:
        session.add(
            OrderPhone(
                order_id=order.id,
                phone=phone,
                price=unit_price,
                status="pending",
            )
        )

    await wallet_svc.deduct_balance(
        session,
        user.id,
        total,
        ref_type="order",
        ref_id=order.id,
        note=f"Order {order.order_code}",
    )

    await session.commit()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_order_by_code(session: AsyncSession, code: str) -> Order | None:
    code = code if code.startswith("#") else f"#{code}"
    result = await session.execute(
        select(Order).where(Order.order_code == code)
    )
    return result.scalar_one_or_none()


async def list_phones(session: AsyncSession, order_id: int):
    result = await session.execute(
        select(OrderPhone)
        .where(OrderPhone.order_id == order_id)
        .order_by(OrderPhone.id)
    )
    return list(result.scalars().all())


async def list_pending_orders(session: AsyncSession, limit: int = 50):
    result = await session.execute(
        select(Order)
        .where(Order.status.in_(["pending", "processing"]))
        .order_by(Order.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_user_orders(
    session: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_phone(session: AsyncSession, phone_id: int) -> OrderPhone | None:
    result = await session.execute(
        select(OrderPhone).where(OrderPhone.id == phone_id)
    )
    return result.scalar_one_or_none()


async def mark_phone_done(
    session: AsyncSession, phone_id: int, admin_id: int
) -> tuple[bool, str, OrderPhone | None]:
    result = await session.execute(
        select(OrderPhone).where(OrderPhone.id == phone_id).with_for_update()
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        return False, "not_found", None
    if phone.status != "pending":
        return False, "already_processed", phone

    phone.status = "done"
    phone.done_by = admin_id
    phone.done_at = datetime.utcnow()

    await session.flush()
    order = await get_order(session, phone.order_id)
    if order:
        await _recalc_order_status(session, order)

    await session.commit()
    await session.refresh(phone)
    return True, "ok", phone


async def mark_phone_failed(
    session: AsyncSession, phone_id: int, admin_id: int
) -> tuple[bool, str, OrderPhone | None]:
    result = await session.execute(
        select(OrderPhone).where(OrderPhone.id == phone_id).with_for_update()
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        return False, "not_found", None
    if phone.status != "pending":
        return False, "already_processed", phone

    phone.status = "failed"
    phone.done_by = admin_id
    phone.done_at = datetime.utcnow()

    await session.flush()

    order = await get_order(session, phone.order_id)
    if order:
        await wallet_svc.refund_balance(
            session,
            order.user_id,
            phone.price,
            ref_type="order",
            ref_id=order.id,
            note=f"Refund {order.order_code} - {phone.phone}",
        )

    if order:
        await _recalc_order_status(session, order)

    await session.commit()
    await session.refresh(phone)
    return True, "ok", phone


async def _recalc_order_status(session: AsyncSession, order: Order) -> str:
    result = await session.execute(
        select(OrderPhone.status, func.count())
        .where(OrderPhone.order_id == order.id)
        .group_by(OrderPhone.status)
    )
    counts = {row[0]: row[1] for row in result.all()}

    pending = counts.get("pending", 0)
    done = counts.get("done", 0)
    failed = counts.get("failed", 0)
    refunded = counts.get("refunded", 0)
    total = pending + done + failed + refunded

    if total == 0:
        new_status = "cancelled"
    elif pending > 0 and done == 0 and failed == 0:
        new_status = "pending"
    elif pending > 0:
        new_status = "processing"
    elif done == total:
        new_status = "completed"
    elif done > 0 and (failed + refunded) > 0:
        new_status = "partially_completed"
    else:
        new_status = "cancelled"

    order.status = new_status
    await session.flush()
    return new_status


async def cancel_order(
    session: AsyncSession, order_id: int, admin_id: int
) -> tuple[bool, str]:
    result = await session.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        return False, "not_found"
    if order.status not in ("pending", "processing"):
        return False, "not_cancellable"

    result = await session.execute(
        select(OrderPhone).where(
            OrderPhone.order_id == order.id,
            OrderPhone.status == "pending",
        )
    )
    pending_phones = result.scalars().all()

    total_refund = Decimal("0")
    for phone in pending_phones:
        phone.status = "refunded"
        phone.done_by = admin_id
        phone.done_at = datetime.utcnow()
        total_refund += phone.price

    if total_refund > 0:
        await wallet_svc.refund_balance(
            session,
            order.user_id,
            total_refund,
            ref_type="order",
            ref_id=order.id,
            note=f"Cancel {order.order_code}",
        )

    order.status = "cancelled"
    await session.commit()
    return True, "ok"


async def count_pending(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.status.in_(["pending", "processing"]))
    )
    return result.scalar_one()
