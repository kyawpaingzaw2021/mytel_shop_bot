from aiogram import Router, F
from aiogram.types import Message

from services import settings as settings_svc
from bot.keyboards.reply import main_menu

router = Router(name="user_support")


@router.message(F.text == "📞 Support")
async def show_support(message: Message, session):
    contact = await settings_svc.get(session, "support_contact", "")
    lines = ["📞 Support", ""]
    if contact:
        lines.append(f"📱 {contact}")
    else:
        lines.append("📱 Admin ကို ဆက်သွယ်ပါ")
    await message.answer("\n".join(lines), reply_markup=main_menu())
