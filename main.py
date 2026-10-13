import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from core.config import config
from db.session import AsyncSessionLocal
from bot.handlers import router as root_router
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttle import ThrottleMiddleware
from services import settings as settings_svc
from tasks.scheduler import setup_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


async def set_commands(bot: Bot):
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="စတင်"),
            BotCommand(command="menu", description="Menu ဖွင့်"),
            BotCommand(command="topup", description="ငွေဖြည့်"),
        ]
    )


async def on_startup(bot: Bot):
    async with AsyncSessionLocal() as session:
        await settings_svc.load_all(session)
    log.info("Settings loaded")


async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(ThrottleMiddleware(rate=0.4))
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_router(root_router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("Scheduler started")

    await on_startup(bot)
    await set_commands(bot)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
