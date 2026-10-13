from aiogram import Router, F
from aiogram.types import Message

from core.config import config
from bot.keyboards.reply import admin_menu


router = Router(name="admin_menu")


def _is_admin(user, tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


@router.message(F.text == "🏠 Main Menu")
async def back_main(message: Message, user=None):
    from bot.keyboards.reply import main_menu as m
    if _is_admin(user, message.from_user.id):
        await message.answer("🛡 Admin Menu", reply_markup=admin_menu())
    else:
        await message.answer("🏠 Main Menu", reply_markup=m())


@router.message(F.text == "📦 Items")
async def menu_items(message: Message, user=None):
    if not _is_admin(user, message.from_user.id):
        return
    from bot.keyboards.inline import items_admin_kb
    await message.answer("📦 Items စီမံခန့်ခွဲမှု", reply_markup=items_admin_kb())


@router.message(F.text == "🧾 Orders")
async def menu_orders(message: Message, user=None):
    if not _is_admin(user, message.from_user.id):
        return
    from bot.handlers.admin.orders import show_pending_list
    await show_pending_list(message)


@router.message(F.text == "💳 Topups")
async def menu_topups(message: Message, user=None):
    if not _is_admin(user, message.from_user.id):
        return
    from bot.handlers.admin.topups import show_pending_topups
    await show_pending_topups(message)


@router.message(F.text == "👥 Users")
async def menu_users(message: Message, user=None):
    if not _is_admin(user, message.from_user.id):
        return
    from bot.keyboards.inline import users_menu_kb
    await message.answer("👥 Users", reply_markup=users_menu_kb())


@router.message(F.text == "🎚 Tiers")
async def menu_tiers(message: Message, user=None):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return
    from bot.keyboards.inline import tiers_admin_kb
    await message.answer("🎚 Tiers", reply_markup=tiers_admin_kb())


@router.message(F.text == "🛡 Admins")
async def menu_admins(message: Message, user=None):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return
    from bot.keyboards.inline import admins_admin_kb
    await message.answer("🛡 Admins", reply_markup=admins_admin_kb())


@router.message(F.text == "⚙️ Settings")
async def menu_settings(message: Message, session, user=None):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return
    from services import settings as settings_svc
    from bot.keyboards.inline import settings_kb
    await settings_svc.load_all(session)
    keys = [
        "payment_kpay", "payment_wave", "payment_name",
        "topup_min", "topup_max", "reminder_interval",
        "escalate_time", "notic_channel_id", "admin_group_id",
        "daily_report_time", "maintenance", "maintenance_message",
        "welcome_message", "support_contact",
    ]
    await message.answer("⚙️ Settings", reply_markup=settings_kb(keys))


@router.message(F.text == "📊 Report")
async def menu_report(message: Message, user=None):
    if not _is_admin(user, message.from_user.id):
        return
    from bot.keyboards.inline import report_kb
    await message.answer("📊 Report", reply_markup=report_kb())
