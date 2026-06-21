"""
Клавиатуры и кнопки бота.
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Налоги и ставки", callback_data="menu_taxes"),
        InlineKeyboardButton(text="📋 Проводки", callback_data="menu_entries"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Календарь сдачи", callback_data="menu_calendar"),
        InlineKeyboardButton(text="💼 УСН / ОСНО", callback_data="menu_systems"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Кадровый учёт", callback_data="menu_hr"),
        InlineKeyboardButton(text="🏢 ЕНС / ЕНП", callback_data="menu_ens"),
    )
    builder.row(
        InlineKeyboardButton(text="🔖 СПОТ (с 06.2026)", callback_data="menu_spot"),
        InlineKeyboardButton(text="🏭 СЭЗ / Запорожье", callback_data="menu_sez"),
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ О боте", callback_data="menu_tarifs"),
        InlineKeyboardButton(text="📞 Помощь", callback_data="menu_help"),
    )
    return builder.as_markup()


def taxes_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="НДС 22%", callback_data="tax_nds"),
        InlineKeyboardButton(text="УСН", callback_data="tax_usn"),
    )
    builder.row(
        InlineKeyboardButton(text="ОСНО / прибыль", callback_data="tax_osno"),
        InlineKeyboardButton(text="НДФЛ", callback_data="tax_ndfl"),
    )
    builder.row(
        InlineKeyboardButton(text="Взносы МСП", callback_data="tax_msp"),
        InlineKeyboardButton(text="Взносы ИП", callback_data="tax_ip"),
    )
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="menu_back"))
    return builder.as_markup()


def back_keyboard(callback: str = "menu_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← В меню", callback_data=callback)]
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no"),
        ]
    ])


# ─── Быстрые команды (reply keyboard) ────────────────────────────────────────

def quick_commands_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Меню"),
        KeyboardButton(text="❓ Помощь"),
    )
    builder.row(
        KeyboardButton(text="🔄 Сбросить диалог"),
        KeyboardButton(text="ℹ️ О боте"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
