from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import select
from core.config import config
from db.session import AsyncSessionLocal
from db.models.order import Order
from services import order as order_svc
from services import user as user_svc
from services import notification as notif
from services import settings as settings_svc


async def cancel_old_orders(bot: Bot):
    async with AsyncSessionLocal() as session:
        hours = int(await settings_svc.get(session, "auto_cancel_hours", 24))
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await session.execute(select(Order).where(Order.status.in_(["pending", "processing"]), Order.created_at < cutoff))
        orders = result.scalars().all()
        if not orders: return
        cancelled = 0
        for order in orders:
            ok, reason = await order_svc.cancel_order(session, order.id, admin_id=config.SUPER_ADMIN_ID)
            if not ok: continue
            cancelled += 1
            buyer = await user_svc.get_by_id(session, order.user_id)
            if buyer:
                await notif.send_user(bot, buyer.telegram_id, f"⚠️ <b>Order အလိုအလျောက် ပယ်ဖျက်ခံရပါသည်</b>\n\n🧾 Order: {order.order_code}\n💰 Refund: {int(order.total):,} Ks")
        if cancelled and config.ADMIN_GROUP_ID:
            await notif.send_admin_group(bot, f"🚨 <b>Auto Cancel</b>\n\nOrder {cancelled} ခု Auto Cancel ဖြစ်သွားပါပြီ။")
