from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    select_item = State()
    enter_qty = State()
    enter_phones = State()
    confirm = State()


class TopupFlow(StatesGroup):
    enter_amount = State()
    send_screenshot = State()
