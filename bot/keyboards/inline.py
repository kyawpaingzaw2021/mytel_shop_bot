from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def items_kb(items: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"📦 {item.name}",
            callback_data=f"item:{item.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def tier_prices_kb(items: list, tier_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=item.name,
            callback_data=f"tierprice:{item.id}:{tier_id}",
        )
    builder.button(text="✅ ပြီးပါပြီ", callback_data="tierprices_done")
    builder.adjust(1)
    return builder.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="✅ အတည်ပြု", callback_data="order_confirm"),
            InlineKeyboardButton(text="❌ ပယ်", callback_data="order_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def balance_low_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="💰 Topup လုပ်မယ်", callback_data="topup_start")],
        [InlineKeyboardButton(text="🔢 Qty လျှော့မယ်", callback_data="order_qty_again")],
        [InlineKeyboardButton(text="❌ ပယ်", callback_data="order_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def phone_actions_kb(order_id: int, phone_id: int, status: str) -> InlineKeyboardMarkup | None:
    if status != "pending":
        return None
    kb = [
        [
            InlineKeyboardButton(
                text="✅ Done", callback_data=f"ph_done:{order_id}:{phone_id}"
            ),
            InlineKeyboardButton(
                text="❌ Fail", callback_data=f"ph_fail:{order_id}:{phone_id}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def order_actions_kb(order_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🚫 Cancel", callback_data=f"ord_cancel:{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def topup_actions_kb(topup_id: int) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(
                text="✅ Approve", callback_data=f"tp_ok:{topup_id}"
            ),
            InlineKeyboardButton(
                text="❌ Reject", callback_data=f"tp_no:{topup_id}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def role_change_kb(user_id: int, current_role: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current_role == "user":
        builder.button(text="🏪 Reseller ဖြစ်စေ", callback_data=f"ur:reseller:{user_id}")
    builder.button(text="🚫 Ban", callback_data=f"ur:ban:{user_id}")
    builder.button(text="✅ Unban", callback_data=f"ur:unban:{user_id}")
    builder.button(text="💰 Wallet", callback_data=f"ur:wallet:{user_id}")
    builder.adjust(1)
    return builder.as_markup()


def tier_action_kb(tier_id: int) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="✏️ နာမည်ပြင်", callback_data=f"tier_edit:{tier_id}"),
            InlineKeyboardButton(text="🗑 ဖျက်", callback_data=f"tier_del:{tier_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def copy_tier_kb(source_tier_id: int, target_tier_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📋 Copy လုပ်မယ်", callback_data=f"copyfrom:{source_tier_id}:{target_tier_id}")],
        [InlineKeyboardButton(text="⏭ ကျော်မယ်", callback_data=f"copyfrom:skip:{target_tier_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def item_actions_kb(item_id: int, status: str) -> InlineKeyboardMarkup:
    toggle_text = "🚫 ပိတ်" if status == "active" else "✅ ဖွင့်"
    kb = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"item_toggle:{item_id}"),
            InlineKeyboardButton(text="🗑 ဖျက်", callback_data=f"item_del:{item_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def pagination_kb(prefix: str, page: int, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️ ရှေ့", callback_data=f"{prefix}:{page - 1}")
    if has_next:
        builder.button(text="နောက် ➡️", callback_data=f"{prefix}:{page + 1}")
    builder.adjust(2)
    return builder.as_markup()


def yes_no_kb(prefix: str, ref_id: int | str = 0) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="✅ ဟုတ်", callback_data=f"{prefix}:yes:{ref_id}"),
            InlineKeyboardButton(text="❌ မဟုတ်", callback_data=f"{prefix}:no:{ref_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def items_admin_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Item အသစ်", callback_data="items:add")],
        [InlineKeyboardButton(text="📋 စာရင်းကြည့်", callback_data="items:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def users_menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📋 အားလုံး", callback_data="users:all")],
        [InlineKeyboardButton(text="🔍 ရှာ", callback_data="users:search")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def user_detail_kb(user_id: int, role: str, banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if role == "user":
        builder.button(text="🏪 Reseller ဖြစ်စေ", callback_data=f"ur:reseller:{user_id}")
    if banned:
        builder.button(text="✅ Unban", callback_data=f"ur:unban:{user_id}")
    else:
        builder.button(text="🚫 Ban", callback_data=f"ur:ban:{user_id}")
    builder.button(text="💰 Wallet History", callback_data=f"ur:wallet:{user_id}")
    builder.adjust(1)
    return builder.as_markup()


def tiers_admin_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Tier အသစ်", callback_data="tier:add")],
        [InlineKeyboardButton(text="📋 စာရင်း", callback_data="tier:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admins_admin_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Admin ထည့်", callback_data="admin:add")],
        [InlineKeyboardButton(text="📋 စာရင်း", callback_data="admin:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def settings_kb(keys: list[str]) -> InlineKeyboardMarkup:
    labels = {
        "payment_kpay": "KPay",
        "payment_wave": "Wave",
        "payment_name": "Payment Name",
        "topup_min": "Topup Min",
        "topup_max": "Topup Max",
        "reminder_interval": "Reminder (min)",
        "escalate_time": "Escalate (min)",
        "notic_channel_id": "Notic Channel ID",
        "admin_group_id": "Admin Group ID",
        "daily_report_time": "Daily Report Time",
        "maintenance": "Maintenance",
        "maintenance_message": "Maintenance Msg",
        "welcome_message": "Welcome Msg",
        "support_contact": "Support Contact",
    }
    builder = InlineKeyboardBuilder()
    for k in keys:
        builder.button(text=labels.get(k, k), callback_data=f"set:{k}")
    builder.adjust(2)
    return builder.as_markup()


def report_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📅 ဒီနေ့", callback_data="rep:today")],
        [InlineKeyboardButton(text="📆 ဒီအပတ်", callback_data="rep:week")],
        [InlineKeyboardButton(text="🗓 ဒီလ", callback_data="rep:month")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def tiers_kb(tiers: list, prefix: str = "picktier") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tier in tiers:
        builder.button(text=tier.name, callback_data=f"{prefix}:{tier.id}")
    builder.adjust(1)
    return builder.as_markup()


def tiers_pick_kb(tiers: list, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tier in tiers:
        builder.button(
            text=tier.name, callback_data=f"ur_tier:{user_id}:{tier.id}"
        )
    builder.adjust(1)
    return builder.as_markup()
