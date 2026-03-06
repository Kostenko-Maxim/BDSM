from aiogram.fsm.state import State, StatesGroup


class BroadcastFSM(StatesGroup):
    waiting_content = State()
    choosing_channels = State()
    confirm_action = State()
    picking_date = State()
    picking_hour = State()
    picking_minute = State()
