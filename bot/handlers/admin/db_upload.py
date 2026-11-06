from aiogram import Router, F, Bot
from aiogram.types import Message
from core.config import config
import os
import subprocess

router = Router(name="db_upload")

SUDO = "/usr/bin/sudo"
PSQL = "/usr/bin/psql"
SYSTEMCTL = "/usr/bin/systemctl"


@router.message(F.document)
async def handle_db_upload(message: Message, bot: Bot):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return
    
    doc = message.document
    file_name = doc.file_name or ""
    
    if not file_name.endswith(".sql"):
        await message.reply("❌ .sql ဖိုင်ပဲ ပို့ပါ။")
        return
    
    await message.reply("⏳ ဖိုင်ကို ဒေါင်းလုပ်နေပါတယ်...")
    
    try:
        backup_dir = os.path.expanduser("~/backups")
        os.makedirs(backup_dir, exist_ok=True)
        file_path = os.path.join(backup_dir, file_name)
        
        await bot.download(doc, destination=file_path)
        
        await message.reply(f"✅ ဖိုင် ဒေါင်းလုပ်ပြီးပါပြီ - {file_name}\n⏳ Database ကို ပြန် Restore လုပ်နေပါတယ်...")
        
        # 1. API (uvicorn) ကို ခေတ္တ ရပ်မယ် (Database ကို လွတ်အောင်)
        subprocess.run([SUDO, SYSTEMCTL, "stop", "mytel-webapp"], check=True)
        
        # 2. ရှိပြီးသား Connection တွေကို ဖျက်မယ်
        subprocess.run(
            [SUDO, "-u", "postgres", PSQL, "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'mytel_shop' AND pid <> pg_backend_pid();"],
            check=True, capture_output=True,
            cwd="/tmp"  # 🔴 cwd ကို /tmp ကို ပြောင်းမယ် (Permission Error ဖြေရှင်းဖို့)
        )
        
        # 3. Database ကို ဖျက်မယ်
        subprocess.run(
            [SUDO, "-u", "postgres", PSQL, "-c", "DROP DATABASE IF EXISTS mytel_shop;"],
            check=True, capture_output=True,
            cwd="/tmp"
        )
        
        # 4. Database အသစ် ဆောက်မယ်
        subprocess.run(
            [SUDO, "-u", "postgres", PSQL, "-c", "CREATE DATABASE mytel_shop OWNER mytel;"],
            check=True, capture_output=True,
            cwd="/tmp"
        )
        
        # 5. Backup ဖိုင်ကို ပြန်ထည့်မယ်
        with open(file_path, "r") as f:
            subprocess.run(
                [SUDO, "-u", "postgres", PSQL, "-d", "mytel_shop"],
                stdin=f, check=True, capture_output=True,
                cwd="/tmp"
            )
        
        # 6. စစ်ဆေးမယ်
        result = subprocess.run(
            [SUDO, "-u", "postgres", PSQL, "-d", "mytel_shop", "-t", "-c", "SELECT COUNT(*) FROM users;"],
            check=True, capture_output=True, text=True,
            cwd="/tmp"
        )
        user_count = result.stdout.strip()
        
        await message.reply(
            f"✅ <b>Database ပြန် Restore လုပ်ပြီးပါပြီ!</b>\n\n"
            f"📁 ဖိုင်: {file_name}\n"
            f"👥 Users: {user_count} ယောက်"
        )
        
        # 7. Service တွေ ပြန် Run မယ်
        subprocess.run([SUDO, SYSTEMCTL, "start", "mytel-webapp"], check=True)
        subprocess.run([SUDO, SYSTEMCTL, "restart", "mytel-bot"], check=True)
        
        await message.reply("✅ Service တွေ ပြန် Restart လုပ်ပြီးပါပြီ။")
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        await message.reply(f"❌ Command Error: {stderr}")
        # Error တက်ရင်လည်း Service ကို ပြန် Run မယ်
        subprocess.run([SUDO, SYSTEMCTL, "start", "mytel-webapp"], check=False)
    except Exception as e:
        await message.reply(f"❌ Error တက်ပါတယ်: {str(e)}")
        subprocess.run([SUDO, SYSTEMCTL, "start", "mytel-webapp"], check=False)
