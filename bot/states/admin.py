from aiogram.fsm.state import State, StatesGroup


class AddItemFlow(StatesGroup):
    enter_name = State()
    enter_code = State()
    enter_description = State()
    enter_user_price = State()
    select_tier = State()
    enter_tier_price = State()
    confirm = State()


class AddTierFlow(StatesGroup):
    enter_name = State()
    ask_copy = State()
    select_source = State()
    confirm = State()


class AddAdminFlow(StatesGroup):
    enter_telegram_id = State()
    enter_role = State()


class SettingFlow(StatesGroup):
    select_key = State()
    enter_value = State()


class UserManageFlow(StatesGroup):
    search = State()
    select_user = State()
    select_tier_for_reseller = State()
