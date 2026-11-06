from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.reply import cancel_menu, main_menu
from bot.keyboards.inline import (
    items_kb,
    confirm_order_kb,
    balance_low_kb,
)
from bot.states.order import OrderFlow
from db.session import AsyncSessionLocal
from services import item as item_svc
from services import order as order_svc
from services import wallet as wallet_svc
from services import validation as val
from services import notification as notif
from core.config import config

router = Router(name="user_order")


@router.message(F.text == "🛒 Order")
async def start_order(message: Message, state: FSMContext, session, user=None):
    if user is None:
        await message.answer("❌ Admin account ဖြင့် order တင်၍ မရပါ")
        return

    items = await item_svc.list_active(session)
    if not items:
        await message.answer("📦 ခေတ္တ Item မရှိသေးပါ")
        return

    lines = []
    for it in items:
        price = await item_svc.get_price(session, it.id, user.tier_id if user.role == "reseller" else None)
        if price is None:
            continue
        lines.append(f"📦 {it.name}\n💰 {int(price):,} Ks")

    if not lines:
        await message.answer("📦 ခေတ္တ Item မရှိသေးပါ")
        return

    available = []
    for it in items:
        price = await item_svc.get_price(session, it.id, user.tier_id if user.role == "reseller" else None)
        if price is not None:
            available.append(it)

    await state.set_state(OrderFlow.select_item)
    await message.answer(
        "🛒 Data ရွေးချယ်ပါ\n\n" + "\n\n".join(lines),
        reply_markup=items_kb(available),
    )


@router.callback_query(OrderFlow.select_item, F.data.startswith("item:"))
async def choose_item(callback: CallbackQuery, state: FSMContext, session, user=None):
    item_id = int(callback.data.split(":")[1])
    item = await item_svc.get_item(session, item_id)
    if item is None or item.status != "active":
        await callback.answer("❌ Item မရှိပါ", show_alert=True)
        return

    tier_id = user.tier_id if user.role == "reseller" else None
    price = await item_svc.get_price(session, item_id, tier_id)
    if price is None:
        await callback.answer("❌ ဒီ Item က သင့် tier အတွက် မရပါ", show_alert=True)
        return

    await state.update_data(item_id=item_id, unit_price=str(price), item_name=item.name)
    await state.set_state(OrderFlow.enter_qty)
    await callback.message.edit_text(
        f"📦 {item.name}\n💰 {int(price):,} Ks / တစ်ခု\n\n"
        f"🔢 ဘယ်နှစ်ခု ဝယ်မလဲ? (1-100)"
    )
    await callback.answer()


@router.message(OrderFlow.enter_qty)
async def enter_qty(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=main_menu())
        return
    if not text.isdigit():
        await message.answer("❌ နံပါတ်ပဲ ရိုက်ပါ")
        return
    qty = int(text)
    if not val.validate_qty(qty):
        await message.answer("❌ 1 မှ 100 အတွင်း ရိုက်ပါ")
        return

    data = await state.get_data()
    await state.update_data(qty=qty)
    await state.set_state(OrderFlow.enter_phones)
    await message.answer(
        f"📱 Phone နံပါတ် {qty} ခု ရိုက်ထည့်ပါ\n\n"
        f"(တစ်ကြောင်းတစ်ခု)\n\n"
        f"ဥပမာ —\n09651234567\n09651234568",
        reply_markup=cancel_menu(),
    )


@router.message(OrderFlow.enter_phones)
async def enter_phones(message: Message, state: FSMContext, session, user=None):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=main_menu())
        return

    data = await state.get_data()
    qty = data["qty"]
    phones = val.parse_phones(text)
    ok, err = val.validate_phones_list(phones, qty)
    if not ok:
        if err.startswith("phone_count_mismatch"):
            await message.answer(f"❌ Phone {qty} ခု လိုပါတယ် (ရိုက်ထားတာ {len(phones)} ခု)")
        elif err.startswith("phone_invalid"):
            await message.answer(f"❌ Phone မှားနေပါတယ် — {err.split(':', 1)[1]}")
        elif err == "phone_duplicate":
            await message.answer("❌ Phone ထပ်နေပါတယ်")
        else:
            await message.answer("❌ Phone မှားနေပါတယ်")
        return

    unit_price = Decimal(data["unit_price"])
    total = unit_price * qty
    balance = await wallet_svc.get_balance(session, user.id)

    if balance < total:
        short = total - balance
        await state.update_data(phones=phones)
        await message.answer(
            f"❌ Balance မလုံလောက်ပါ\n\n"
            f"💰 လိုအပ်: {int(total):,} Ks\n"
            f"💰 လက်ရှိ: {int(balance):,} Ks\n"
            f"💰 လိုသေး: {int(short):,} Ks",
            reply_markup=balance_low_kb(),
        )
        return

    await state.update_data(phones=phones)
    await state.set_state(OrderFlow.confirm)

    phone_lines = "\n".join(f"• {p}" for p in phones)
    await message.answer(
        f"📋 Order အတည်ပြုပါ\n\n"
        f"📦 {data['item_name']}\n"
        f"🔢 Qty: {qty}\n"
        f"💰 Total: {int(total):,} Ks\n\n"
        f"📱 Phones:\n{phone_lines}\n\n"
        f"💰 လက်ရှိ Balance: {int(balance):,} Ks\n"
        f"💰 ကျန်မည့် Balance: {int(balance - total):,} Ks",
        reply_markup=confirm_order_kb(),
    )


@router.callback_query(OrderFlow.confirm, F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery, state: FSMContext, session, user=None, bot: Bot = None):
    data = await state.get_data()
    await state.clear()

    item = await item_svc.get_item(session, data["item_id"])
    if item is None:
        await callback.message.edit_text("❌ Item မရှိတော့ပါ")
        await callback.answer()
        return

    try:
        order = await order_svc.create_order(
            session=session,
            user=user,
            item=item,
            qty=data["qty"],
            phones=data["phones"],
            unit_price=Decimal(data["unit_price"]),
        )
    except ValueError:
        await callback.message.edit_text("❌ Balance မလုံလောက်တော့ပါ")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"✅ Order တင်ပြီးပါပြီ\n\n"
        f"🧾 Order {order.order_code}\n"
        f"📦 {order.item_name} × {order.qty}\n"
        f"💰 {int(order.total):,} Ks\n\n"
        f"⏳ Admin မှ Data ဖြည့်ပေးပါမည်"
    )
    await callback.answer()

    if bot:
        await _notify_admin_new_order(bot, order, user, session)


@router.callback_query(F.data == "order_cancel")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ ပယ်လိုက်ပါပြီ")
    await callback.answer()


@router.callback_query(F.data == "order_qty_again")
async def qty_again(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderFlow.enter_qty)
    await callback.message.edit_text("🔢 Qty ပြန်ရိုက်ပါ (1-100)")
    await callback.answer()


@router.callback_query(F.data == "topup_start")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    from bot.handlers.user.wallet import start_topup
    await state.clear()
    await callback.message.edit_text("💰 Topup စတင်ပါမည်...\n\nWallet menu ကို ပြန်ဖွင့်ပါ")
    await callback.answer()


async def _notify_admin_new_order(bot: Bot, order, user, session):
    from bot.keyboards.inline import phone_actions_kb
    phones = await order_svc.list_phones(session, order.id)

    role_label = "🏪 Reseller" if order.role_at_order == "reseller" else "👤 User"
    lines = [
        f"🆕 Order {order.order_code}",
        "",
        f"{role_label}: {user.full_name or '-'} (ID: {user.telegram_id})",
        f"📦 {order.item_name}",
        f"🔢 Qty: {order.qty}",
        f"💰 Total: {int(order.total):,} Ks",
        "",
        "📱 Phones:",
    ]
    for i, p in enumerate(phones, 1):
        lines.append(f"{i}. {p.phone}")

    text = "\n".join(lines)

    if config.ADMIN_GROUP_ID:
        await notif.send_admin_group(bot, text)
        for p in phones:
            kb = phone_actions_kb(order.id, p.id, p.status)
            await notif.send_admin_group(
                bot,
                f"📱 {order.order_code} — {p.phone}",
                reply_markup=kb,
            )
