from datetime import datetime, timedelta

from aiogram import Bot

from core.config import config
from db.session import AsyncSessionLocal
from services import notification as notif
from bot.handlers.superadmin.report import build_report


async def send_daily(bot: Bot):
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=1)
        text = await build_report(session, start, end)

    if config.ADMIN_GROUP_ID:
        await notif.send_admin_group(bot, text)
    await notif.send_user(bot, config.SUPER_ADMIN_ID, text)
