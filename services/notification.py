from decimal import Decimal
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from core.config import config


async def send_user(bot: Bot, telegram_id: int, text: str, **kwargs):
    try:
        return await bot.send_message(telegram_id, text, **kwargs)
    except TelegramAPIError:
        return None


async def send_admin_group(bot: Bot, text: str, **kwargs):
    if not config.ADMIN_GROUP_ID:
        return None
    try:
        return await bot.send_message(config.ADMIN_GROUP_ID, text, **kwargs)
    except TelegramAPIError:
        return None


def fmt_amount(amount: Decimal | float) -> str:
    return f"{int(amount):,}"
