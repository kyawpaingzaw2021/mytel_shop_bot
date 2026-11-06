from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from db.session import AsyncSessionLocal
from services import order as order_svc
from services import user as user_svc
from services import notification as notif
from core.config import config
import logging
import re

logger = logging.getLogger("admin_notify")
router = Router(name="admin_notify")


@router.callback_query(F.data.startswith("ph_done:"))
async def ph_done(callback: CallbackQuery, bot: Bot):
    await callback.answer("⏳ လုပ်ဆောင်နေပါသည်...")
    try:
        _, order_id, phone_id = callback.data.split(":")
        async with AsyncSessionLocal() as session:
            ok, reason, phone = await order_svc.mark_phone_done(session, int(phone_id), callback.from_user.id)
            if not ok:
                await callback.message.answer(f"❌ {reason}")
                return
            try: await callback.message.edit_reply_markup(reply_markup=None)
            except Exception: pass
            order = await order_svc.get_order(session, int(order_id))
            if order:
                buyer = await user_svc.get_by_id(session, order.user_id)
                if buyer:
                    await notif.send_user(bot, buyer.telegram_id, f"✅ Data ဖြည့်ပြီးပါပြီ\n\n📱 {phone.phone}\n📦 {order.item_name}")
    except Exception as e:
        logger.error(f"ph_done error: {e}")


@router.callback_query(F.data.startswith("ph_fail:"))
async def ph_fail(callback: CallbackQuery, bot: Bot):
    await callback.answer("⏳ လုပ်ဆောင်နေပါသည်...")
    try:
        _, order_id, phone_id = callback.data.split(":")
        await callback.message.answer(f"📝 <b>Fail ဖြစ်ရတဲ့ အကြောင်းပြချက် ရိုက်ထည့်ပါ</b>\n\nOrder ID: <code>{order_id}</code>\nPhone ID: <code>{phone_id}</code>\n\n<i>ဒီစာကို Reply ပြန်ပြီး ရိုက်ပါ။</i>")
        try: await callback.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
    except Exception as e:
        logger.error(f"ph_fail error: {e}")


@router.message(F.reply_to_message, F.chat.id == config.ADMIN_GROUP_ID)
async def handle_fail_reason(message: Message, bot: Bot):
    if not message.text: return
    reply_text = message.reply_to_message.text or ""
    if "Fail ဖြစ်ရတဲ့" not in reply_text and "Phone ID:" not in reply_text: return
    try:
        order_match = re.search(r"Order ID:\s*(\d+)", reply_text)
        phone_match = re.search(r"Phone ID:\s*(\d+)", reply_text)
        if not order_match or not phone_match: return
        order_id = int(order_match.group(1))
        phone_id = int(phone_match.group(1))
        reason = message.text.strip()
        async with AsyncSessionLocal() as session:
            ok, status_msg, phone = await order_svc.mark_phone_failed(session, phone_id, message.from_user.id)
            if not ok:
                await message.reply(f"⚠️ {status_msg}")
                return
            order = await order_svc.get_order(session, order_id)
            if order:
                buyer = await user_svc.get_by_id(session, order.user_id)
                if buyer:
                    text = f"❌ <b>Data ဖြည့်မပေးနိုင်ပါ</b>\n\n📱 {phone.phone}\n💰 Refund: {int(phone.price):,} Ks\n\n📝 <b>အကြောင်းပြချက် -</b> {reason}"
                    await notif.send_user(bot, buyer.telegram_id, text)
            await message.reply(f"✅ User ဆီသို့ ပို့ပြီးပါပြီ။")
    except Exception as e:
        logger.error(f"handle_fail_reason error: {e}")
