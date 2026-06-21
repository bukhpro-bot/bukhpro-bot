"""
Конфигурация бота — читает переменные из .env / Railway окружения.
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    # Telegram
    bot_token: str
    admin_ids: list[int]

    # Anthropic
    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2048

    # PostgreSQL
    database_url: str = ""

    # Лимиты сообщений (единый бесплатный лимит для всех)
    messages_per_day: int = 30

    # История контекста
    context_history_length: int = 20  # сообщений в памяти

    # Webhook (если нужен)
    webhook_host: str = ""
    webhook_path: str = "/webhook"
    webapp_host: str = "0.0.0.0"
    webapp_port: int = 8080


def load_config() -> Config:
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("BOT_TOKEN не задан! Добавьте в .env или Railway Variables.")

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY не задан!")

    admin_raw = os.environ.get("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_raw.split(",") if x.strip().isdigit()]

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        anthropic_api_key=anthropic_key,
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=int(os.environ.get("MAX_TOKENS", "2048")),
        database_url=os.environ.get("DATABASE_URL", ""),
        messages_per_day=int(os.environ.get("MESSAGES_PER_DAY", "30")),
        webhook_host=os.environ.get("WEBHOOK_HOST", ""),
        webapp_port=int(os.environ.get("PORT", "8080")),
    )
