"""
Обработчики команд и callback-запросов главного меню.
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import (
    get_or_create_user,
    get_user_stats,
    get_admin_stats,
    reset_dialog_history,
    get_dialog_history,
)
from keyboards import (
    main_menu_keyboard,
    taxes_menu_keyboard,
    back_keyboard,
    quick_commands_keyboard,
)
from states import AdminState, FeedbackState

logger = logging.getLogger(__name__)
router = Router()


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, config: Config, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
    )

    text = (
        "👋 <b>Добро пожаловать в БухПро 2026!</b>\n\n"
        "Я ваш персональный бухгалтерский консультант. "
        "Задайте любой вопрос по бухгалтерии, налогам или отчётности — "
        "я отвечу на основе актуального законодательства РФ 2026.\n\n"
        "🧾 <b>Что я умею:</b>\n"
        "• НДС, налог на прибыль, НДФЛ, УСН, ОСНО\n"
        "• Типовые проводки и учётная политика\n"
        "• Зарплата, кадровый учёт, страховые взносы\n"
        "• ЕНС / ЕНП, налоговый календарь 2026\n"
        "• СПОТ, СЭЗ Запорожской области (рег. 90)\n"
        "• ФСБУ 6, 26, 25, 5 — основные средства, НМА, запасы\n\n"
        f"💬 <b>Лимит:</b> {config.messages_per_day} вопросов в день\n\n"
        "Начните с вопроса или выберите тему в меню 👇"
    )

    await message.answer(text, reply_markup=quick_commands_keyboard())
    await message.answer("📊 Главное меню:", reply_markup=main_menu_keyboard())


# ─── /menu ────────────────────────────────────────────────────────────────────

@router.message(Command("menu"))
@router.message(F.text == "📊 Меню")
async def cmd_menu(message: Message, config: Config, state: FSMContext):
    await state.clear()
    await message.answer("📊 Главное меню:", reply_markup=main_menu_keyboard())


# ─── /help ────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message, config: Config):
    text = (
        "🆘 <b>Справка по БухПро 2026</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/menu — открыть меню\n"
        "/status — мой статус и лимиты\n"
        "/reset — сбросить историю диалога\n"
        "/nalogi — налоговый календарь\n"
        "/usn — расчёт УСН\n"
        "/provodki — типовые проводки\n"
        "/spravka — справочник ставок\n\n"
        "<b>Как использовать:</b>\n"
        "Просто напишите вопрос в свободной форме:\n"
        "• «Как рассчитать НДС с аванса?»\n"
        "• «Проводки при продаже ОС»\n"
        "• «Когда сдавать 6-НДФЛ в 2026?»\n"
        "• «Ставки взносов для МСП в 2026»\n\n"
        f"💬 Ежедневный лимит: {config.messages_per_day} вопросов\n"
        "Лимит обнуляется в полночь по московскому времени."
    )
    await message.answer(text, reply_markup=back_keyboard())


# ─── /status ──────────────────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message, config: Config):
    stats = await get_user_stats(message.from_user.id)
    msgs_used = stats.get("today_messages", 0)
    limit = config.messages_per_day
    remaining = max(0, limit - msgs_used)

    text = (
        f"👤 <b>Ваш статус</b>\n\n"
        f"🆓 <b>Тариф:</b> Бесплатный\n"
        f"💬 <b>Использовано сегодня:</b> {msgs_used} / {limit}\n"
        f"⏳ <b>Осталось:</b> {remaining} вопросов\n\n"
        f"Лимит обновляется каждую ночь в 00:00 МСК."
    )
    await message.answer(text, reply_markup=back_keyboard())


# ─── /subscribe (О боте) ──────────────────────────────────────────────────────

@router.message(Command("subscribe"))
@router.message(F.text == "ℹ️ О боте")
async def cmd_subscribe(message: Message, config: Config):
    await _show_about(message, config)


async def _show_about(message: Message, config: Config):
    text = (
        "ℹ️ <b>О боте БухПро 2026</b>\n\n"
        "Бот полностью <b>бесплатный</b>.\n\n"
        "📚 <b>База знаний включает:</b>\n"
        "• Все налоги РФ (НДС 22%, УСН, ОСНО, НДФЛ)\n"
        "• Страховые взносы (МСП, ИП, АУСН)\n"
        "• ФСБУ 6/2020, ФСБУ 26/2020, ФСБУ 25/2018, ФСБУ 5/2019\n"
        "• ЕНС / ЕНП — сальдо, зачёт, возврат\n"
        "• СПОТ с 1 июня 2026 — пошаговое руководство\n"
        "• СЭЗ Запорожской области (регион 90): льготы, ставки, условия\n"
        "• Туристический налог, АУСН, МСП-взносы\n"
        "• Кадровый учёт, зарплата, отпускные, больничные\n"
        "• Типовые проводки по всем разделам учёта\n\n"
        f"💬 <b>Ежедневный лимит:</b> {config.messages_per_day} вопросов\n\n"
        "🤖 <i>Работает на базе Claude Anthropic</i>"
    )
    await message.answer(text, reply_markup=back_keyboard())


# ─── /reset ───────────────────────────────────────────────────────────────────

@router.message(Command("reset"))
@router.message(F.text == "🔄 Сбросить диалог")
async def cmd_reset(message: Message, config: Config):
    await reset_dialog_history(message.from_user.id)
    await message.answer(
        "🔄 <b>История диалога сброшена.</b>\n"
        "Начнём с чистого листа! Задайте ваш вопрос.",
        reply_markup=quick_commands_keyboard(),
    )


# ─── Тематические команды ─────────────────────────────────────────────────────

@router.message(Command("nalogi"))
async def cmd_nalogi(message: Message, config: Config):
    await message.answer(
        "📅 Налоговый календарь 2026 — напишите свой вопрос:\n"
        "Например: «Когда подавать декларацию по НДС за Q2 2026?»",
        reply_markup=back_keyboard(),
    )


@router.message(Command("usn"))
async def cmd_usn(message: Message, config: Config):
    await message.answer(
        "📊 Расчёт налога УСН — напишите свой вопрос:\n"
        "Например: «Как рассчитать налог УСН 15% за полугодие, доходы 1 000 000, расходы 700 000?»",
        reply_markup=back_keyboard(),
    )


@router.message(Command("provodki"))
async def cmd_provodki(message: Message, config: Config):
    await message.answer(
        "📋 Типовые бухгалтерские проводки — напишите свой вопрос:\n"
        "Например: «Проводки при покупке ОС за счёт кредита»",
        reply_markup=back_keyboard(),
    )


@router.message(Command("spravka"))
async def cmd_spravka(message: Message, config: Config):
    text = (
        "📖 <b>Справочник ставок и лимитов 2026</b>\n\n"
        "<b>НДС:</b> 22% (общая), 10% (льготные), 0%\n"
        "<b>Налог на прибыль:</b> 25% / 20% (до 2025)\n"
        "<b>НДФЛ:</b> 13%/15%/18%/20%/22% (прогрессия)\n"
        "<b>УСН «Доходы»:</b> 6% (до 60 млн) / 8% (60–450 млн)\n"
        "<b>УСН «Доходы – Расходы»:</b> 15% / 20%\n\n"
        "<b>Взносы 2026:</b>\n"
        "ФСС НС: от 0,2% до 8,5%\n"
        "ОМС: 5,1% (с зарплаты выше МРП)\n\n"
        "Задайте уточняющий вопрос!"
    )
    await message.answer(text, reply_markup=back_keyboard())


@router.message(Command("calendar"))
async def cmd_calendar(message: Message, config: Config):
    await message.answer(
        "📅 Налоговый календарь 2026 — задайте свой вопрос:\n"
        "Например: «Когда сдавать 4-ФСС за 9 месяцев 2026?»",
        reply_markup=back_keyboard(),
    )


# ─── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config, state: FSMContext):
    if message.from_user.id not in config.admin_ids:
        await message.answer("⛔ У вас нет прав администратора.")
        return

    stats = await get_admin_stats()
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        f"👥 Всего пользователей: <b>{stats.get('total_users', 0)}</b>\n"
        f"📊 Активных сегодня: <b>{stats.get('today_active', 0)}</b>\n"
        f"💬 Сообщений сегодня: <b>{stats.get('today_messages', 0)}</b>\n\n"
        f"🤖 Модель: <code>{config.model}</code>\n"
        f"📋 Лимит/день: {config.messages_per_day} сообщ"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="← Закрыть", callback_data="admin_close"))

    await message.answer(text, reply_markup=builder.as_markup())


# ─── Callback-хендлер главного меню ──────────────────────────────────────────

@router.callback_query(F.data.startswith("menu_"))
async def process_menu_callback(callback: CallbackQuery, config: Config, state: FSMContext):
    action = callback.data.replace("menu_", "")
    await callback.answer()

    if action == "back":
        await callback.message.edit_text("📊 Главное меню:", reply_markup=main_menu_keyboard())

    elif action == "taxes":
        text = (
            "💰 <b>Налоги и ставки 2026</b>\n\n"
            "Выберите интересующий налог или задайте вопрос в чат:"
        )
        await callback.message.edit_text(text, reply_markup=taxes_menu_keyboard())

    elif action == "entries":
        await callback.message.edit_text(
            "📋 <b>Бухгалтерские проводки</b>\n\n"
            "Напишите хозяйственную операцию — я покажу типовые проводки.\n"
            "Например: <i>«Поступление товара от поставщика с НДС»</i>",
            reply_markup=back_keyboard(),
        )

    elif action == "calendar":
        await callback.message.edit_text(
            "📅 <b>Налоговый календарь 2026</b>\n\n"
            "Задайте вопрос о сроках сдачи отчётности или уплаты налогов.\n"
            "Например: <i>«Когда платить НДС за 3 квартал 2026?»</i>",
            reply_markup=back_keyboard(),
        )

    elif action == "systems":
        await callback.message.edit_text(
            "🏢 <b>Системы налогообложения</b>\n\n"
            "• <b>УСН</b> — упрощённая система (6% или 15%)\n"
            "• <b>ОСНО</b> — общая система (НДС + налог на прибыль)\n"
            "• <b>АУСН</b> — автоматизированная УСН\n\n"
            "Задайте вопрос по любой системе!",
            reply_markup=back_keyboard(),
        )

    elif action == "hr":
        await callback.message.edit_text(
            "👥 <b>Кадровый учёт и зарплата</b>\n\n"
            "• Начисление и выплата зарплаты\n"
            "• Отпускные, больничные, командировочные\n"
            "• Страховые взносы (ОПС, ОМС, ОСС)\n"
            "• 6-НДФЛ, РСВ, ЕФС-1\n\n"
            "Задайте вопрос!",
            reply_markup=back_keyboard(),
        )

    elif action == "ens":
        await callback.message.edit_text(
            "🏦 <b>Единый налоговый счёт (ЕНС) и ЕНП</b>\n\n"
            "• Пополнение ЕНС\n"
            "• Сальдо ЕНС — как проверить\n"
            "• Зачёт и возврат переплаты\n"
            "• Уведомления об исчисленных суммах\n\n"
            "Задайте вопрос!",
            reply_markup=back_keyboard(),
        )

    elif action == "spot":
        await callback.message.edit_text(
            "🔖 <b>СПОТ — с 1 июня 2026</b>\n\n"
            "Система прослеживаемости операций с товарами.\n"
            "Кого касается, как подключиться, какие документы нужны?\n\n"
            "Задайте вопрос — я расскажу пошагово!",
            reply_markup=back_keyboard(),
        )

    elif action == "sez":
        await callback.message.edit_text(
            "🏭 <b>СЭЗ Запорожской области (регион 90)</b>\n\n"
            "Свободная экономическая зона — льготы:\n"
            "• Налог на прибыль: 2% вместо 25%\n"
            "• НДС: освобождение или пониженные ставки\n"
            "• Страховые взносы: 7,6% вместо 30%\n\n"
            "Задайте вопрос по условиям и льготам СЭЗ!",
            reply_markup=back_keyboard(),
        )

    elif action == "tarifs":
        # О боте — бот бесплатный
        await callback.message.edit_text(
            f"ℹ️ <b>О боте БухПро 2026</b>\n\n"
            "Бот полностью <b>бесплатный</b>.\n\n"
            "📚 <b>База знаний включает:</b>\n"
            "• Все налоги РФ (НДС 22%, УСН, ОСНО, НДФЛ)\n"
            "• ФСБУ 6, 26, 25, 5 — основные средства, НМА, запасы\n"
            "• ЕНС / ЕНП — сальдо, зачёт, возврат\n"
            "• СПОТ с 1 июня 2026\n"
            "• СЭЗ Запорожской области (регион 90)\n"
            "• Кадровый учёт и зарплата\n\n"
            f"💬 <b>Ежедневный лимит:</b> {config.messages_per_day} вопросов\n\n"
            "🤖 <i>Работает на базе Claude Anthropic</i>",
            reply_markup=back_keyboard(),
        )

    elif action == "help":
        await callback.message.edit_text(
            "🆘 <b>Помощь</b>\n\n"
            "Просто напишите вопрос в свободной форме:\n"
            "• «Как рассчитать НДС с аванса?»\n"
            "• «Проводки при продаже ОС»\n"
            "• «Когда сдавать 6-НДФЛ в 2026?»\n\n"
            f"Лимит: {config.messages_per_day} вопросов в день.\n"
            "Лимит обнуляется в полночь по МСК.",
            reply_markup=back_keyboard(),
        )


# ─── Callback — подменю налогов ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tax_"))
async def process_tax_callback(callback: CallbackQuery, config: Config):
    tax = callback.data.replace("tax_", "")
    await callback.answer()

    descriptions = {
        "nds": "НДС 22% — основная ставка с 2025 года. Задайте вопрос!",
        "usn": "УСН — упрощённая система налогообложения. 6% (доходы) или 15% (доходы–расходы). Задайте вопрос!",
        "osno": "ОСНО — налог на прибыль 25% (с 2025 г.). Задайте вопрос!",
        "ndfl": "НДФЛ — прогрессивная шкала: 13%/15%/18%/20%/22%. Задайте вопрос!",
        "msp": "Страховые взносы МСП — 15% вместо 30% с выплат выше МРОТ. Задайте вопрос!",
        "ip": "Взносы ИП за себя в 2026 году. Задайте вопрос!",
    }

    text = descriptions.get(tax, "Задайте вопрос по этой теме!")
    await callback.message.edit_text(text, reply_markup=back_keyboard("menu_taxes"))


# ─── Admin callbacks ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_"))
async def process_admin_callback(callback: CallbackQuery, config: Config, state: FSMContext):
    action = callback.data.replace("admin_", "")
    await callback.answer()

    if action == "close":
        await callback.message.delete()

    elif action == "broadcast":
        if callback.from_user.id not in config.admin_ids:
            return
        await state.set_state(AdminState.waiting_broadcast)
        await callback.message.edit_text(
            "📣 <b>Рассылка</b>\n\n"
            "Напишите сообщение для отправки всем пользователям.\n"
            "Или /cancel для отмены.",
        )


# ─── Отмена FSM ───────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=quick_commands_keyboard())
    else:
        await message.answer("Нечего отменять.", reply_markup=quick_commands_keyboard())
