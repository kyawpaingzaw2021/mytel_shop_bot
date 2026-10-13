from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.config import config
from bot.keyboards.reply import admin_menu, cancel_menu
from bot.states.admin import SettingFlow
from services import settings as settings_svc
from services import audit as audit_svc

router = Router(name="sa_settings")


LABELS = {
    "payment_kpay": "KPay number",
    "payment_wave": "Wave number",
    "payment_name": "Payment account name",
    "topup_min": "Topup Min (Ks) — integer",
    "topup_max": "Topup Max (Ks) — integer",
    "reminder_interval": "Reminder (minutes) — integer",
    "escalate_time": "Escalate (minutes) — integer",
    "notic_channel_id": "Notic Channel ID (negative int)",
    "admin_group_id": "Admin Group ID (negative int)",
    "daily_report_time": "Daily Report Time (HH:MM)",
    "maintenance": "Maintenance — on/off",
    "maintenance_message": "Maintenance message",
    "welcome_message": "Welcome message",
    "support_contact": "Support contact (@username or phone)",
}


def _is_super(tg_id: int) -> bool:
    return tg_id == config.SUPER_ADMIN_ID


@router.callback_query(F.data.startswith("set:"))
async def pick_setting(callback: CallbackQuery, state: FSMContext, session):
    if not _is_super(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    current = await settings_svc.get(session, key, "(မရှိ)")
    await state.set_state(SettingFlow.enter_value)
    await state.update_data(key=key)
    await callback.message.answer(
        f"⚙️ {key}\n\n"
        f"📌 အခု — {current}\n\n"
        f"📝 {LABELS.get(key, '')}\n\n"
        f"Value အသစ် ရိုက်ပါ",
        reply_markup=cancel_menu(),
    )
    await callback.answer()


@router.message(SettingFlow.enter_value)
async def save_value(message: Message, state: FSMContext, session):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=admin_menu())
        return

    data = await state.get_data()
    key = data["key"]

    ok, err = _validate(key, text)
    if not ok:
        await message.answer(f"❌ {err}")
        return

    await settings_svc.update(session, key, text, message.from_user.id)
    await audit_svc.log(
        session,
        message.from_user.id,
        "setting_change",
        "setting",
        None,
        new_value={key: text},
    )
    await state.clear()
    await message.answer(
        f"✅ သိမ်းပြီးပါပြီ\n\n⚙️ {key} = {text}",
        reply_markup=admin_menu(),
    )


def _validate(key: str, value: str) -> tuple[bool, str]:
    if key in ("topup_min", "topup_max", "reminder_interval", "escalate_time"):
        if not value.isdigit():
            return False, "နံပါတ်ပဲ ရိုက်ပါ"
    if key in ("notic_channel_id", "admin_group_id"):
        v = value.lstrip("-")
        if not v.isdigit():
            return False, "Integer (negative) ရိုက်ပါ"
    if key == "daily_report_time":
        parts = value.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return False, "HH:MM format ရိုက်ပါ (ဥပမာ 00:00)"
    if key == "maintenance":
        if value not in ("on", "off"):
            return False, "on / off ပဲ ရိုက်ပါ"
    return True, ""
