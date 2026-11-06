from datetime import datetime
from aiogram import Bot
from sqlalchemy import select, func
from db.session import AsyncSessionLocal
from services import notification as notif
from core.config import config
from db.models.order import Order, OrderPhone
from db.models.user import User


async def send_daily(bot: Bot):
    async with AsyncSessionLocal() as session:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        res_o = await session.execute(select(Order).where(Order.created_at >= today_start))
        orders = res_o.scalars().all()
        total = len(orders)
        completed = sum(1 for o in orders if o.status in ["completed", "partially_completed"])
        revenue = sum(float(o.total) for o in orders if o.status in ["completed", "partially_completed"])
        res_u = await session.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))
        new_users = res_u.scalar_one()
        text = f"📊 <b>Daily Report</b>\n📅 {today_start.strftime('%Y-%m-%d')}\n\n🧾 Orders: {total}\n✅ Completed: {completed}\n💰 Revenue: {int(revenue):,} Ks\n👥 New Users: {new_users}"
        if config.ADMIN_GROUP_ID: await notif.send_admin_group(bot, text)
        await notif.send_user(bot, config.SUPER_ADMIN_ID, text)
