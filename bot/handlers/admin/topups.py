from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from core.config import config
from bot.keyboards.reply import admin_menu
from services import topup as topup_svc
from services import user as user_svc
from services import audit as audit_svc
from services import notification as notif

router = Router(name="admin_topups")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


async def show_pending_topups(message: Message):
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        rows = await topup_svc.list_pending(session)
    if not rows:
        await message.answer("✅ Pending topup မရှိပါ", reply_markup=admin_menu())
        return
    lines = [f"💳 Pending Topups ({len(rows)})", ""]
    for t in rows:
        lines.append(
            f"⏳ #{t.id} — {int(t.amount):,} Ks | "
            f"{t.created_at.strftime('%m-%d %H:%M')}"
        )
    await message.answer("\n".join(lines), reply_markup=admin_menu())


@router.callback_query(F.data.startswith("tp_ok:"))
async def approve(callback: CallbackQuery, session, user=None, bot: Bot = None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    topup_id = int(callback.data.split(":")[1])
    ok, reason, topup = await topup_svc.approve(
        session, topup_id, callback.from_user.id
    )
    if not ok:
        await callback.answer(f"❌ {reason}", show_alert=True)
        return

    await audit_svc.log(
        session,
        admin_id=callback.from_user.id,
        action="topup_approve",
        target_type="topup",
        target_id=topup.id,
    )
    await callback.answer("✅ Approve")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    buyer = await user_svc.get_by_id(session, topup.user_id)
    if bot and buyer:
        await notif.send_user(
            bot,
            buyer.telegram_id,
            f"✅ ငွေဖြည့်ပြီးပါပြီ\n\n"
            f"💰 {int(topup.amount):,} Ks",
        )


@router.callback_query(F.data.startswith("tp_no:"))
async def reject(callback: CallbackQuery, session, user=None, bot: Bot = None):
    if not _is_admin(user, callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    topup_id = int(callback.data.split(":")[1])
    ok, reason, topup = await topup_svc.reject(
        session, topup_id, callback.from_user.id
    )
    if not ok:
        await callback.answer(f"❌ {reason}", show_alert=True)
        return

    await audit_svc.log(
        session,
        admin_id=callback.from_user.id,
        action="topup_reject",
        target_type="topup",
        target_id=topup.id,
    )
    await callback.answer("❌ Reject")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    buyer = await user_svc.get_by_id(session, topup.user_id)
    if bot and buyer:
        await notif.send_user(
            bot,
            buyer.telegram_id,
            f"❌ ငွေဖြည့် မအောင်မြင်ပါ\n\n"
            f"💰 {int(topup.amount):,} Ks\n\n"
            f"📞 Support ကို ဆက်သွယ်ပါ",
        )
