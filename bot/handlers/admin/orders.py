from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from core.config import config
from bot.keyboards.reply import admin_menu
from bot.keyboards.inline import phone_actions_kb, order_actions_kb
from services import order as order_svc
from services import user as user_svc
from services import audit as audit_svc
from services import notification as notif

router = Router(name="admin_orders")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


async def show_pending_list(message: Message):
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        orders = await order_svc.list_pending_orders(session)
    if not orders:
        await message.answer("✅ Pending order မရှိပါ", reply_markup=admin_menu())
        return
    lines = [f"🧾 Pending Orders ({len(orders)})", ""]
    for o in orders:
        lines.append(
            f"⏳ {o.order_code} — {o.item_name} × {o.qty}\n"
            f"   💰 {int(o.total):,} Ks | {o.created_at.strftime('%m-%d %H:%M')}"
        )
    await message.answer("\n".join(lines), reply_markup=admin_menu())


@router.callback_query(F.data.startswith("ph_done:"))
async def ph_done(callback: CallbackQuery, session, user=None, bot: Bot = None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    _, order_id, phone_id = callback.data.split(":")
    ok, reason, phone = await order_svc.mark_phone_done(
        session, int(phone_id), callback.from_user.id
    )
    if not ok:
        await callback.answer(f"❌ {reason}", show_alert=True)
        return

    await audit_svc.log(
        session,
        admin_id=callback.from_user.id,
        action="phone_done",
        target_type="order_phone",
        target_id=phone.id,
    )
    await callback.answer("✅ Done")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    order = await order_svc.get_order(session, int(order_id))
    buyer = await user_svc.get_by_id(session, order.user_id) if order else None

    if bot and order:
        await notif.send_user(
            bot,
            buyer.telegram_id,
            f"✅ Data ဖြည့်ပြီးပါပြီ\n\n"
            f"📱 {phone.phone}\n"
            f"📦 {order.item_name}",
        )
        await _maybe_finalize(bot, session, order)


@router.callback_query(F.data.startswith("ph_fail:"))
async def ph_fail(callback: CallbackQuery, session, user=None, bot: Bot = None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    _, order_id, phone_id = callback.data.split(":")
    ok, reason, phone = await order_svc.mark_phone_failed(
        session, int(phone_id), callback.from_user.id
    )
    if not ok:
        await callback.answer(f"❌ {reason}", show_alert=True)
        return

    await audit_svc.log(
        session,
        admin_id=callback.from_user.id,
        action="phone_failed",
        target_type="order_phone",
        target_id=phone.id,
    )
    await callback.answer("❌ Fail + Refund")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    order = await order_svc.get_order(session, int(order_id))
    buyer = await user_svc.get_by_id(session, order.user_id) if order else None

    if bot and order:
        await notif.send_user(
            bot,
            buyer.telegram_id,
            f"❌ Data ဖြည့်မပေးနိုင်ပါ\n\n"
            f"📱 {phone.phone}\n"
            f"💰 Refund: {int(phone.price):,} Ks",
        )
        await _maybe_finalize(bot, session, order)


async def _maybe_finalize(bot: Bot, session, order):
    phones = await order_svc.list_phones(session, order.id)
    if any(p.status == "pending" for p in phones):
        return
    await order_svc._recalc_order_status(session, order)
    await session.commit()

    buyer = await user_svc.get_by_id(session, order.user_id)
    summary = "\n".join(
        f"{'✅' if p.status == 'done' else '❌'} {p.phone}" for p in phones
    )
    await notif.send_user(
        bot,
        buyer.telegram_id,
        f"✅ Order {order.order_code} ပြီးစီးပါပြီ\n\n"
        f"📦 {order.item_name} × {order.qty}\n\n"
        f"📱 ရလဒ်များ:\n{summary}",
    )

    from services import masking as mask
    channel_text = (
        f"✅ {order.order_code} ပြီးစီး\n\n"
        f"📦 {order.item_name} × {order.qty}\n"
        f"💰 {int(order.total):,} Ks\n"
        f"👤 {mask.mask_username(buyer.username, buyer.full_name)}\n"
        f"📱 {mask.mask_phone(phones[0].phone) if phones else '-'}"
    )
    await notif.send_channel(bot, channel_text)
