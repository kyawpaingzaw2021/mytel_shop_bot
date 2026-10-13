from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from core.config import config
from bot.keyboards.reply import main_menu

router = Router(name="user_start")


@router.message(CommandStart())
async def cmd_start(message: Message, user=None):
    if user is None and message.from_user.id == config.SUPER_ADMIN_ID:
        from bot.keyboards.reply import admin_menu
        await message.answer(
            "👋 Super Admin မင်္ဂလာပါ\n\n"
            "🛡 Admin Menu ကို အောက်မှာ ရွေးပါ",
            reply_markup=admin_menu(),
        )
        return

    name = message.from_user.full_name or "မိတ်ဆွေ"
    role_text = ""
    if user and user.role == "reseller":
        role_text = "\n🏪 Reseller အဖြစ် ဝင်ရောက်ထားပါတယ်"

    await message.answer(
        f"👋 မင်္ဂလာပါ {name} ရေ\n\n"
        f"📱 Mytel Data Shop မှ ကြိုဆိုပါတယ်{role_text}\n\n"
        f"🛒 Data ဝယ်ရန် — Order နှိပ်ပါ\n"
        f"💰 ငွေဖြည့်ရန် — Wallet နှိပ်ပါ",
        reply_markup=main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, user=None):
    if message.from_user.id == config.SUPER_ADMIN_ID or (user and user.role == "admin"):
        from bot.keyboards.reply import admin_menu
        await message.answer("🛡 Admin Menu", reply_markup=admin_menu())
        return
    await message.answer("🏠 Main Menu", reply_markup=main_menu())
