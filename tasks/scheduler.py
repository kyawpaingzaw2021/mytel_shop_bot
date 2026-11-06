from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from core.config import config
from tasks import reminder, report, auto_cancel, backup


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.TZ)
    scheduler.add_job(reminder.check_pending, IntervalTrigger(minutes=10), args=[bot], id="reminder")
    scheduler.add_job(auto_cancel.cancel_old_orders, IntervalTrigger(hours=1), args=[bot], id="auto_cancel")
    scheduler.add_job(report.send_daily, CronTrigger(hour=0, minute=0), args=[bot], id="daily_report")
    scheduler.add_job(backup.send_db_backup, CronTrigger(hour="0,12", minute=0), args=[bot], id="db_backup")
    return scheduler
