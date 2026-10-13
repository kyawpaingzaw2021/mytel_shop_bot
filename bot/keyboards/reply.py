from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🛒 Order"), KeyboardButton(text="💰 Wallet")],
        [KeyboardButton(text="📜 History"), KeyboardButton(text="📞 Support")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📦 Items"), KeyboardButton(text="🧾 Orders")],
        [KeyboardButton(text="💳 Topups"), KeyboardButton(text="👥 Users")],
        [KeyboardButton(text="🎚 Tiers"), KeyboardButton(text="🛡 Admins")],
        [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="📊 Report")],
        [KeyboardButton(text="🏠 Main Menu")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def cancel_menu() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="❌ ပယ်မယ်")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def skip_menu() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="⏭ ကျော်မယ်")], [KeyboardButton(text="❌ ပယ်မယ်")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
