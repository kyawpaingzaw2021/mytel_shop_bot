from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import select, func
from core.config import config
from db.session import AsyncSessionLocal
from db.models.order import Order
from db.models.topup import Topup
from services import notification as notif


async def check_pending(bot: Bot):
    async with AsyncSessionLocal() as session:
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        res = await session.execute(select(func.count()).select_from(Order).where(Order.status.in_(["pending", "processing"]), Order.created_at < cutoff))
        pending_orders = res.scalar_one()
        res2 = await session.execute(select(func.count()).select_from(Topup).where(Topup.status == "pending", Topup.created_at < cutoff))
        pending_topups = res2.scalar_one()
        if pending_orders == 0 and pending_topups == 0: return
        if config.ADMIN_GROUP_ID:
            await notif.send_admin_group(bot, f"⏰ <b>Pending Reminder</b>\n\n🧾 Orders: {pending_orders}\n💳 Topups: {pending_topups}")
