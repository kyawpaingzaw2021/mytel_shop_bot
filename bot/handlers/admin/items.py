from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from core.config import config
from bot.keyboards.reply import admin_menu, cancel_menu, skip_menu
from bot.keyboards.inline import (
    items_admin_kb,
    item_actions_kb,
    tiers_pick_kb,
)
from bot.states.admin import AddItemFlow
from services import item as item_svc
from services import tier as tier_svc
from services import audit as audit_svc

router = Router(name="admin_items")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


@router.callback_query(F.data == "items:add")
async def start_add(callback: CallbackQuery, state: FSMContext, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await state.set_state(AddItemFlow.enter_name)
    await callback.message.answer(
        "📦 Item အသစ်\n\n1️⃣ Name ရိုက်ပါ (ဥပမာ — Mytel 1GB (7days))",
        reply_markup=cancel_menu(),
    )
    await callback.answer()


@router.message(AddItemFlow.enter_name)
async def add_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    if not (2 <= len(text) <= 64):
        await message.answer("❌ 2-64 လုံး ရိုက်ပါ")
        return
    await state.update_data(name=text)
    await state.set_state(AddItemFlow.enter_code)
    await message.answer("2️⃣ Code ရိုက်ပါ (ဥပမာ — MYTEL1GB)")


@router.message(AddItemFlow.enter_code)
async def add_code(message: Message, state: FSMContext, session):
    text = (message.text or "").strip().upper()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    if not (2 <= len(text) <= 32):
        await message.answer("❌ 2-32 လုံး (A-Z, 0-9, _) ရိုက်ပါ")
        return
    if await item_svc.get_by_code(session, text):
        await message.answer("❌ Code ဒီအတိုင်း ရှိပြီးသား")
        return
    await state.update_data(code=text)
    await state.set_state(AddItemFlow.enter_description)
    await message.answer(
        "3️⃣ Description ရိုက်ပါ (optional)",
        reply_markup=skip_menu(),
    )


@router.message(AddItemFlow.enter_description)
async def add_desc(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    desc = None if text == "⏭ ကျော်မယ်" else text
    await state.update_data(description=desc)
    await state.set_state(AddItemFlow.enter_user_price)
    await message.answer("4️⃣ User Price ရိုက်ပါ (Ks)")


@router.message(AddItemFlow.enter_user_price)
async def add_user_price(message: Message, state: FSMContext, session):
    text = (message.text or "").strip().replace(",", "")
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    try:
        price = Decimal(text)
    except Exception:
        await message.answer("❌ နံပါတ် ရိုက်ပါ")
        return
    if price <= 0:
        await message.answer("❌ 0 ထက် ကြီးရမယ်")
        return

    await state.update_data(user_price=str(price))
    tiers = await tier_svc.list_all(session)
    if not tiers:
        data = await state.get_data()
        await _finalize_add(message, state, session, user=None, tier_prices={})
        return

    await state.set_state(AddItemFlow.select_tier)
    await state.update_data(
        tier_ids=[t.id for t in tiers],
        tier_index=0,
        tier_prices={},
    )
    await message.answer(
        f"5️⃣ {tiers[0].name} Tier Price ရိုက်ပါ (Ks)",
        reply_markup=skip_menu(),
    )


@router.message(AddItemFlow.select_tier)
async def add_tier_price(message: Message, state: FSMContext, session):
    text = (message.text or "").strip().replace(",", "")
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return

    data = await state.get_data()
    tier_ids = data["tier_ids"]
    idx = data["tier_index"]
    tier_prices = data.get("tier_prices", {})
    tiers = await tier_svc.list_all(session)
    current_tier = tiers[idx]

    if text != "⏭ ကျော်မယ်":
        try:
            price = Decimal(text)
            if price <= 0:
                raise ValueError
            tier_prices[str(current_tier.id)] = str(price)
        except Exception:
            await message.answer("❌ နံပါတ် ရိုက်ပါ (သို့) ကျော်မယ်")
            return

    idx += 1
    if idx >= len(tier_ids):
        await state.update_data(tier_prices=tier_prices)
        await _finalize_add(message, state, session, user=None)
        return

    next_tier = tiers[idx]
    await state.update_data(tier_index=idx, tier_prices=tier_prices)
    await message.answer(f"5️⃣ {next_tier.name} Tier Price ရိုက်ပါ (Ks)")


async def _finalize_add(message, state, session, user=None, tier_prices=None):
    data = await state.get_data()
    await state.clear()
    tp = tier_prices if tier_prices is not None else {
        int(k): Decimal(v) for k, v in data.get("tier_prices", {}).items()
    }

    item = await item_svc.create_item(
        session=session,
        name=data["name"],
        code=data["code"],
        description=data.get("description"),
        user_price=Decimal(data["user_price"]),
        tier_prices=tp,
    )
    await audit_svc.log(
        session,
        admin_id=message.from_user.id,
        action="item_create",
        target_type="item",
        target_id=item.id,
        new_value={"name": item.name, "code": item.code},
    )
    await message.answer(
        f"✅ Item ထည့်ပြီးပါပြီ\n\n📦 {item.name}\n💰 {int(item.user_price):,} Ks",
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data == "items:list")
async def list_items(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    items = await item_svc.list_all(session)
    if not items:
        await callback.message.edit_text("📦 Item မရှိသေးပါ")
        await callback.answer()
        return
    lines = ["📋 Items", ""]
    for it in items:
        flag = "✅" if it.status == "active" else "🚫"
        lines.append(f"{flag} {it.name} — {int(it.user_price):,} Ks")
    await callback.message.edit_text("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith("item_toggle:"))
async def toggle(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    item_id = int(callback.data.split(":")[1])
    item = await item_svc.get_item(session, item_id)
    if item is None:
        await callback.answer("❌", show_alert=True)
        return
    await item_svc.toggle_status(session, item)
    await callback.answer(f"✅ {item.status}")
    kb = item_actions_kb(item.id, item.status)
    await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("item_del:"))
async def delete(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    item_id = int(callback.data.split(":")[1])
    item = await item_svc.get_item(session, item_id)
    if item is None:
        await callback.answer("❌", show_alert=True)
        return
    await item_svc.delete_item(session, item)
    await callback.message.edit_text(f"🗑 {item.name} ဖျက်ပြီးပါပြီ")
    await callback.answer()
