from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select, func

from core.config import config
from db.session import AsyncSessionLocal
from db.models.order import Order
from db.models.topup import Topup
from services import notification as notif
from services import settings as settings_svc


async def check_pending(bot: Bot):
    async with AsyncSessionLocal() as session:
        interval = int(await settings_svc.get(session, "reminder_interval", 30))
        escalate = int(await settings_svc.get(session, "escalate_time", 120))

        cutoff = datetime.utcnow() - timedelta(minutes=interval)
        escalate_cutoff = datetime.utcnow() - timedelta(minutes=escalate)

        result = await session.execute(
            select(func.count()).select_from(Order).where(
                Order.status.in_(["pending", "processing"]),
                Order.created_at < cutoff,
            )
        )
        pending_orders = result.scalar_one()

        result = await session.execute(
            select(func.count()).select_from(Topup).where(
                Topup.status == "pending",
                Topup.created_at < cutoff,
            )
        )
        pending_topups = result.scalar_one()

        if pending_orders == 0 and pending_topups == 0:
            return

        if config.ADMIN_GROUP_ID:
            await notif.send_admin_group(
                bot,
                f"⏰ Reminder\n\n"
                f"🧾 Pending Orders: {pending_orders}\n"
                f"💳 Pending Topups: {pending_topups}\n\n"
                f"({interval} မိနစ်ကျော်)",
            )

        # Escalate to super admin
        result = await session.execute(
            select(func.count()).select_from(Order).where(
                Order.status.in_(["pending", "processing"]),
                Order.created_at < escalate_cutoff,
            )
        )
        old_orders = result.scalar_one()

        if old_orders > 0:
            await notif.send_user(
                bot,
                config.SUPER_ADMIN_ID,
                f"🚨 Escalation\n\n"
                f"🧾 Orders pending {escalate} min+: {old_orders}",
            )
