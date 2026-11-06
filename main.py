import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from core.config import config
from db.session import AsyncSessionLocal
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttle import ThrottleMiddleware
from services import settings as settings_svc
from tasks.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")


async def on_error(event: ErrorEvent):
    log.error(f"Update {event.update_id} တွင် Error တက်ပါသည်: {event.exception}")


def build_dispatcher() -> Dispatcher:
    from bot.handlers.user.start import router as user_start
    from bot.handlers.admin.notify import router as admin_notify
    from bot.handlers.admin.db_upload import router as db_upload
    dp = Dispatcher()
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(ThrottleMiddleware(rate=0.4))
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(user_start)
    dp.include_router(admin_notify)
    dp.include_router(db_upload)
    return dp


async def main():
    print("✅ Bot စတင်နေပါပြီ...")
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    dp.errors.register(on_error)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    async with AsyncSessionLocal() as session:
        await settings_svc.load_all(session)
    await bot.set_my_commands([BotCommand(command="start", description="App ဖွင့်ရန်")])
    print("✅ Polling စတင်နေပါပြီ...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
