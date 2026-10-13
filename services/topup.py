from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.topup import Topup
from services import wallet as wallet_svc


async def check_duplicate_ss(session: AsyncSession, ss_file_id: str) -> bool:
    result = await session.execute(
        select(Topup).where(Topup.ss_file_id == ss_file_id)
    )
    return result.scalar_one_or_none() is not None


async def create_topup(
    session: AsyncSession, user_id: int, amount: Decimal, ss_file_id: str
) -> Topup:
    topup = Topup(
        user_id=user_id,
        amount=amount,
        ss_file_id=ss_file_id,
        status="pending",
    )
    session.add(topup)
    await session.commit()
    await session.refresh(topup)
    return topup


async def get_topup(session: AsyncSession, topup_id: int) -> Topup | None:
    result = await session.execute(select(Topup).where(Topup.id == topup_id))
    return result.scalar_one_or_none()


async def list_pending(session: AsyncSession, limit: int = 50):
    result = await session.execute(
        select(Topup)
        .where(Topup.status == "pending")
        .order_by(Topup.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def approve(
    session: AsyncSession, topup_id: int, admin_id: int
) -> tuple[bool, str, Topup | None]:
    result = await session.execute(
        select(Topup).where(Topup.id == topup_id).with_for_update()
    )
    topup = result.scalar_one_or_none()
    if topup is None:
        return False, "not_found", None
    if topup.status != "pending":
        return False, "already_processed", topup

    await wallet_svc.add_balance(
        session,
        topup.user_id,
        topup.amount,
        ref_type="topup",
        ref_id=topup.id,
        note=f"Topup #{topup.id}",
    )

    topup.status = "approved"
    topup.approved_by = admin_id
    await session.commit()
    await session.refresh(topup)
    return True, "ok", topup


async def reject(
    session: AsyncSession, topup_id: int, admin_id: int
) -> tuple[bool, str, Topup | None]:
    result = await session.execute(
        select(Topup).where(Topup.id == topup_id).with_for_update()
    )
    topup = result.scalar_one_or_none()
    if topup is None:
        return False, "not_found", None
    if topup.status != "pending":
        return False, "already_processed", topup

    topup.status = "rejected"
    topup.approved_by = admin_id
    await session.commit()
    await session.refresh(topup)
    return True, "ok", topup
