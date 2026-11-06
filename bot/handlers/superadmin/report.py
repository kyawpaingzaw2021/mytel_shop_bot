from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.config import config
from db.models.order import Order, OrderPhone
from db.models.user import User
from services import notification as notif
from sqlalchemy import select, func

router = Router(name="sa_report")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


async def build_report(session, start: datetime, end: datetime) -> str:
    result = await session.execute(
        select(Order.status, func.count())
        .where(Order.created_at >= start, Order.created_at < end)
        .group_by(Order.status)
    )
    counts = {r[0]: r[1] for r in result.all()}

    result = await session.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.created_at >= start, Order.created_at < end)
    )
    revenue = result.scalar_one()

    result = await session.execute(
        select(func.coalesce(func.sum(OrderPhone.price), 0))
        .where(
            OrderPhone.status == "failed",
            OrderPhone.done_at >= start,
            OrderPhone.done_at < end,
        )
    )
    refund = result.scalar_one()

    result = await session.execute(
        select(func.count()).select_from(User)
        .where(User.created_at >= start, User.created_at < end)
    )
    new_users = result.scalar_one()

    total = sum(counts.values())

    lines = [
        f"📊 Report {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}",
        "━━━━━━━━━━━━━━",
        f"🧾 Orders: {total}",
        f"✅ Completed: {counts.get('completed', 0)}",
        f"⚠️ Partial: {counts.get('partially_completed', 0)}",
        f"❌ Cancelled: {counts.get('cancelled', 0)}",
        f"💰 Revenue: {int(revenue):,} Ks",
        f"💸 Refund: {int(refund):,} Ks",
        f"👥 New Users: {new_users}",
        "━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


@router.callback_query(F.data.startswith("rep:"))
async def show(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    period = callback.data.split(":")[1]
    now = datetime.utcnow()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:  # month
        start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now

    text = await build_report(session, start, end)
    await callback.message.edit_text(text)
    await callback.answer()
