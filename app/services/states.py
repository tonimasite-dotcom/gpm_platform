from aiogram.dispatcher.filters.state import StatesGroup, State


class RegisterState(StatesGroup):
    phone_number = State()
    city = State()
    choice_region = State()
    name = State()
    surname = State()
    middle_name = State()
    date_birth = State()
    nationality = State()
    tools = State()
    confirm_data = State()
    change_data = State()
    in_process_change_data = State()


class OperatorState(StatesGroup):
    city = State()
    region = State()
    order_id = State()
    date = State()
    people_amount = State()
    nationality = State()
    metro = State()
    address = State()
    choice_address = State()
    description = State()
    mode_selection = State()
    shift_description = State()
    price_regular = State()
    price_state = State()
    price_per_hour = State()
    min_time = State()
    check_data = State()
    change_data = State()
    in_process_change_data = State()
    in_change_city = State()
