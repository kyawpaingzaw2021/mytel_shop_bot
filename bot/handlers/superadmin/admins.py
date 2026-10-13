from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.config import config
from bot.keyboards.reply import admin_menu, cancel_menu
from bot.states.admin import AddAdminFlow
from services import audit as audit_svc
from db.session import AsyncSessionLocal
from db.models.admin import Admin
from sqlalchemy import select

router = Router(name="sa_admins")


def _is_super(tg_id: int) -> bool:
    return tg_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data == "admin:add")
async def start_add(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await state.set_state(AddAdminFlow.enter_telegram_id)
    await callback.message.answer(
        "🛡 Admin အသစ်\n\nTelegram ID ရိုက်ပါ",
        reply_markup=cancel_menu(),
    )
    await callback.answer()


@router.message(AddAdminFlow.enter_telegram_id)
async def add_admin_id(message: Message, state: FSMContext, session):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return
    if not text.isdigit():
        await message.answer("❌ နံပါတ်ပဲ ရိုက်ပါ")
        return

    tg_id = int(text)
    result = await session.execute(
        select(Admin).where(Admin.telegram_id == tg_id)
    )
    if result.scalar_one_or_none() is not None:
        await message.answer("❌ ဒီ ID က admin ရှိပြီးသား")
        return

    session.add(
        Admin(telegram_id=tg_id, role="admin", added_by=message.from_user.id)
    )
    await session.commit()
    await audit_svc.log(
        session,
        message.from_user.id,
        "admin_add",
        "admin",
        tg_id,
        new_value={"telegram_id": tg_id, "role": "admin"},
    )
    await state.clear()
    await message.answer(
        f"✅ Admin ထည့်ပြီးပါပြီ\n\n🆔 {tg_id}",
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data == "admin:list")
async def list_admins(callback: CallbackQuery, session):
    if not _is_super(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    result = await session.execute(
        select(Admin).order_by(Admin.created_at)
    )
    rows = result.scalars().all()
    lines = ["🛡 Admins", ""]
    lines.append(f"👑 Super Admin — {config.SUPER_ADMIN_ID}")
    for a in rows:
        flag = "✅" if a.is_active else "🚫"
        lines.append(f"{flag} {a.telegram_id} — {a.role}")
    await callback.message.edit_text("\n".join(lines))
    await callback.answer()
