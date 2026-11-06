import os
import subprocess
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile
from core.config import config


async def send_db_backup(bot: Bot):
    if not config.SUPER_ADMIN_ID: return
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_path = f"/tmp/backup_{date_str}.sql"
    env = os.environ.copy()
    env["PGPASSWORD"] = config.DB_PASSWORD
    cmd = ["pg_dump", "-U", config.DB_USER, "-h", config.DB_HOST, "-p", str(config.DB_PORT), "-d", config.DB_NAME, "-f", file_path]
    try:
        subprocess.run(cmd, env=env, check=True)
        await bot.send_document(chat_id=config.SUPER_ADMIN_ID, document=FSInputFile(file_path), caption=f"🗄️ Backup {date_str}")
    except Exception as e:
        await bot.send_message(config.SUPER_ADMIN_ID, f"⚠️ Backup မအောင်မြင်ပါ: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
