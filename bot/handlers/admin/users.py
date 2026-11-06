from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from core.config import config
from bot.keyboards.reply import admin_menu, cancel_menu
from bot.keyboards.inline import (
    users_menu_kb,
    user_detail_kb,
    tiers_kb,
)
from bot.states.admin import UserManageFlow
from services import user as user_svc
from services import tier as tier_svc
from services import wallet as wallet_svc
from services import audit as audit_svc
from services import notification as notif

router = Router(name="admin_users")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


@router.callback_query(F.data == "users:all")
async def all_users(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    rows = await user_svc.list_users(session, limit=20)
    if not rows:
        await callback.message.edit_text("👥 User မရှိသေးပါ")
        await callback.answer()
        return
    lines = ["👥 Users", ""]
    for u in rows:
        role = {"user": "👤", "reseller": "🏪", "admin": "🛡"}.get(u.role, "?")
        ban = " 🚫" if u.is_banned else ""
        lines.append(f"{role} {u.full_name or '-'} (ID: {u.telegram_id}){ban}")
    await callback.message.edit_text("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "users:search")
async def search_start(callback: CallbackQuery, state: FSMContext, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await state.set_state(UserManageFlow.search)
    await callback.message.answer(
        "🔍 Telegram ID ရိုက်ပါ", reply_markup=cancel_menu()
    )
    await callback.answer()


@router.message(UserManageFlow.search)
async def search_do(message: Message, state: FSMContext, session):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    if not text.isdigit():
        await message.answer("❌ နံပါတ်ပဲ ရိုက်ပါ")
        return
    u = await user_svc.get_by_telegram_id(session, int(text))
    await state.clear()
    if u is None:
        await message.answer("❌ User မတွေ့ပါ", reply_markup=admin_menu())
        return
    await _send_user_detail(message, session, u, reply=True)


async def _send_user_detail(target, session, u, reply: bool = False):
    balance = await wallet_svc.get_balance(session, u.id)
    tier_name = "-"
    if u.tier_id:
        t = await tier_svc.get_tier(session, u.tier_id)
        tier_name = t.name if t else "-"

    text = (
        f"👤 User Detail\n\n"
        f"📛 Name: {u.full_name or '-'}\n"
        f"🔗 Username: @{u.username or '-'}\n"
        f"🆔 Telegram ID: {u.telegram_id}\n"
        f"🎭 Role: {u.role}\n"
        f"🎚 Tier: {tier_name}\n"
        f"💰 Balance: {int(balance):,} Ks\n"
        f"🚫 Banned: {'Yes' if u.is_banned else 'No'}"
    )
    kb = user_detail_kb(u.id, u.role, u.is_banned)
    if reply:
        await target.answer(text, reply_markup=kb)
    else:
        await target.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("ur:reseller:"))
async def to_reseller(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    u = await user_svc.get_by_id(session, user_id)
    if u is None:
        await callback.answer("❌", show_alert=True)
        return
    tiers = await tier_svc.list_all(session)
    if not tiers:
        await callback.answer("❌ Tier မရှိသေးပါ", show_alert=True)
        return
    await callback.message.edit_text(
        "🎚 Tier ရွေးပါ", reply_markup=tiers_kb(tiers, prefix=f"ur_tier:{user_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ur_tier:"))
async def set_reseller_tier(callback: CallbackQuery, session, user=None, bot: Bot = None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    _, user_id, tier_id = callback.data.split(":")
    u = await user_svc.get_by_id(session, int(user_id))
    if u is None:
        await callback.answer("❌", show_alert=True)
        return

    old_role = u.role
    await user_svc.set_role(session, u, "reseller", int(tier_id))
    await audit_svc.log(
        session,
        admin_id=callback.from_user.id,
        action="role_change",
        target_type="user",
        target_id=u.id,
        old_value={"role": old_role},
        new_value={"role": "reseller", "tier_id": int(tier_id)},
    )
    await callback.answer("✅ Reseller ဖြစ်သွားပါပြီ")
    await callback.message.edit_text(f"✅ {u.full_name or u.telegram_id} → Reseller")

    if bot:
        await notif.send_user(
            bot,
            u.telegram_id,
            f"🎉 သင်ဟာ Reseller ဖြစ်သွားပါပြီ",
        )


@router.callback_query(F.data.startswith("ur:ban:"))
async def ban(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    u = await user_svc.get_by_id(session, user_id)
    if u is None:
        await callback.answer("❌", show_alert=True)
        return
    await user_svc.set_banned(session, u, True)
    await audit_svc.log(
        session, callback.from_user.id, "user_ban", "user", u.id
    )
    await callback.answer("🚫 Ban")
    await _send_user_detail(callback, session, u)


@router.callback_query(F.data.startswith("ur:unban:"))
async def unban(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    u = await user_svc.get_by_id(session, user_id)
    if u is None:
        await callback.answer("❌", show_alert=True)
        return
    await user_svc.set_banned(session, u, False)
    await audit_svc.log(
        session, callback.from_user.id, "user_unban", "user", u.id
    )
    await callback.answer("✅ Unban")
    await _send_user_detail(callback, session, u)


@router.callback_query(F.data.startswith("ur:wallet:"))
async def wallet_view(callback: CallbackQuery, session, user=None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    txs = await wallet_svc.list_transactions(session, user_id, limit=10)
    if not txs:
        await callback.answer("Wallet history မရှိပါ", show_alert=True)
        return
    lines = ["💰 Wallet History", ""]
    for tx in txs:
        sign = "+" if tx.amount > 0 else ""
        lines.append(
            f"• {tx.type}: {sign}{int(tx.amount):,} Ks | "
            f"{tx.created_at.strftime('%m-%d %H:%M')}"
        )
    await callback.message.edit_text("\n".join(lines))
    await callback.answer()
