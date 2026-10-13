from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import config
from tasks import reminder, report


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.TZ)

    scheduler.add_job(
        reminder.check_pending,
        IntervalTrigger(minutes=10),
        args=[bot],
        id="reminder",
        replace_existing=True,
    )

    scheduler.add_job(
        report.send_daily,
        CronTrigger(hour=0, minute=0),
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )

    return scheduler
