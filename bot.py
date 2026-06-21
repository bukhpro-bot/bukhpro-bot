"""
Точка входа: создание бота, диспетчера, регистрация хендлеров и мидлвеи.
"""
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiohttp import web

from dotenv import load_dotenv
load_dotenv()

from config import load_config
from database import init_db, close_db
from handlers import commands, messages

logger = logging.getLogger(__name__)


# ─── Health check HTTP сервер (для cloud hosting) ────────────────────────────

async def health_check(request):
    """Ответ на проверку работоспособности от хостинга."""
    return web.Response(text="OK")

async def start_health_server():
    """Запускаем минимальный HTTP сервер для cloud хостинга (Koyeb и т.д.)."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check сервер запущен на порту {port}")
    return runner


# ─── Middleware: прокидывает config во все хендлеры ──────────────────────────

class ConfigMiddleware:
    """Кладёт config в данные обработчика через data['config']."""

    def __init__(self, config):
        self._config = config

    async def __call__(self, handler, event, data):
        data["config"] = self._config
        return await handler(event, data)


# ─── Команды бота (меню в Telegram) ──────────────────────────────────────────

BOT_COMMANDS = [
    BotCommand(command="start",     description="Начать работу / главное меню"),
    BotCommand(command="menu",      description="Открыть меню"),
    BotCommand(command="help",      description="Справка и возможности"),
    BotCommand(command="status",    description="Мой статус и лимиты"),
    BotCommand(command="subscribe", description="О боте"),
    BotCommand(command="reset",     description="Сбросить историю диалога"),
    BotCommand(command="nalogi",    description="Налоговый календарь"),
    BotCommand(command="usn",       description="Расчёт налога УСН"),
    BotCommand(command="provodki",  description="Типовые бухгалтерские проводки"),
    BotCommand(command="spravka",   description="Справочник ставок и лимитов"),
    BotCommand(command="calendar",  description="Налоговый календарь 2026"),
]


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

async def on_startup(bot: Bot, config):
    """Действия при запуске бота."""
    await init_db(config.database_url)
    logger.info("БД инициализирована")

    try:
        await bot.set_my_commands(BOT_COMMANDS)
        logger.info("Команды бота установлены")
    except Exception as e:
        logger.warning(f"Не удалось установить команды: {e}")

    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.id})")

    # Уведомляем администраторов о запуске
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"✅ <b>Бот запущен в облаке!</b>\n"
                f"Модель: <code>{config.model}</code>\n"
                f"БД: {'PostgreSQL' if config.database_url else 'In-Memory'}\n"
                f"Лимит: {config.messages_per_day} сообщ/день",
                parse_mode="HTML",
            )
        except Exception:
            pass  # Администратор ещё не запускал бота — не критично


async def on_shutdown(bot: Bot):
    """Действия при остановке бота."""
    await close_db()
    logger.info("Соединение с БД закрыто")
    await bot.session.close()
    logger.info("Бот остановлен")


# ─── Основная функция ─────────────────────────────────────────────────────────

async def main():
    # Логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    # Конфиг
    config = load_config()
    logger.info(f"Конфиг загружен. Модель: {config.model}")

    # Бот
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Диспетчер с in-memory FSM хранилищем
    dp = Dispatcher(storage=MemoryStorage())

    # ── Middleware ────────────────────────────────────────────────────────────
    config_middleware = ConfigMiddleware(config)
    dp.message.middleware(config_middleware)
    dp.callback_query.middleware(config_middleware)

    # ── Регистрация роутеров ──────────────────────────────────────────────────
    dp.include_router(commands.router)
    dp.include_router(messages.router)

    # ── Startup / Shutdown ────────────────────────────────────────────────────
    async def _startup():
        await on_startup(bot, config)

    async def _shutdown():
        await on_shutdown(bot)

    dp.startup.register(_startup)
    dp.shutdown.register(_shutdown)

    # ── Health check сервер (ОБЯЗАТЕЛЬНО для Koyeb / облачного хостинга) ─────
    health_runner = await start_health_server()

    # ── Запуск polling ────────────────────────────────────────────────────────
    logger.info("Запуск polling...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную (KeyboardInterrupt)")
