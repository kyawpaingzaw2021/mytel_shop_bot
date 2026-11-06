from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.enums import ChatMemberStatus
from core.config import config
import time
import urllib.parse

router = Router(name="user_start")
CHANNEL_LINK = "https://t.me/mytel_data"
BASE_URL = "https://myanmaroperater.wunnatinaye.online/"


def get_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel သို့ ဝင်ရောက်ရန်", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ ဝင်ပြီးပါပြီ (စစ်ဆေးမယ်)", callback_data="check_join")]
    ])


def get_app_kb(ref_id=None):
    base_url = BASE_URL
    if ref_id:
        safe_ref = urllib.parse.quote(str(ref_id))
        base_url += f"?ref={safe_ref}&t={int(time.time())}"
    else:
        base_url += f"?t={int(time.time())}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ဆိုင်ဖွင့်ရန် (Open App)", web_app=WebAppInfo(url=base_url))]
    ])


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not config.NOTIC_CHANNEL_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=config.NOTIC_CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception:
        return True


@router.message(CommandStart(deep_link=True))
async def cmd_start_ref(message: Message, command: CommandObject, bot: Bot):
    ref_id = None
    if command.args and command.args.startswith("ref_"):
        ref_id = command.args.replace("ref_", "")
    subscribed = await is_subscribed(bot, message.from_user.id)
    if not subscribed:
        await message.answer(f"👋 မင်္ဂလာပါ <b>{message.from_user.first_name}</b> ရေ!\n\n⚠️ <b>Channel အရင်ဝင်ပေးပါ။</b>", reply_markup=get_join_kb())
        return
    await message.answer(f"👋 မင်္ဂလာပါ <b>{message.from_user.first_name}</b> ရေ!\n\n📱 <b>Myanmar Operator</b> မှ ကြိုဆိုပါတယ်။", reply_markup=get_app_kb(ref_id))


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    subscribed = await is_subscribed(bot, message.from_user.id)
    if not subscribed:
        await message.answer(f"👋 မင်္ဂလာပါ <b>{message.from_user.first_name}</b> ရေ!\n\n⚠️ <b>Channel အရင်ဝင်ပေးပါ။</b>", reply_markup=get_join_kb())
        return
    await message.answer(f"👋 မင်္ဂလာပါ <b>{message.from_user.first_name}</b> ရေ!\n\n📱 <b>Myanmar Operator</b> မှ ကြိုဆိုပါတယ်။", reply_markup=get_app_kb())


@router.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery, bot: Bot):
    subscribed = await is_subscribed(bot, callback.from_user.id)
    if subscribed:
        await callback.message.edit_text(f"✅ Channel ဝင်ပြီးပါပြီ။", reply_markup=get_app_kb())
        await callback.answer("✅ အောင်မြင်ပါသည်")
    else:
        await callback.answer("❌ Channel မဝင်ရသေးပါဘူး။", show_alert=True)
