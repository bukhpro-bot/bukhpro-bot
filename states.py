"""
FSM состояния для многошаговых диалогов.
"""
from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    """Состояния для команд администратора."""
    wait_user_id = State()      # Ожидание ввода user_id
    wait_ban_id = State()       # Ожидание ввода user_id для бана


class FeedbackState(StatesGroup):
    """Обратная связь / поддержка (расширение на будущее)."""
    wait_message = State()
