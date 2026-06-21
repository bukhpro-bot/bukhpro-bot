"""
База данных PostgreSQL: пользователи, история диалогов, платежи.
Использует asyncpg для async-работы с aiogram.
При отсутствии DATABASE_URL — работает без БД (in-memory режим).
"""
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore
    ASYNCPG_AVAILABLE = False

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальный пул соединений (asyncpg.Pool или None)
_pool = None

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id        BIGINT PRIMARY KEY,
    username       TEXT,
    first_name     TEXT,
    last_name      TEXT,
    joined_at      TIMESTAMPTZ DEFAULT NOW(),
    subscription   TEXT DEFAULT 'free',      -- free | pro | vip
    sub_expires    TIMESTAMPTZ,
    messages_today INT DEFAULT 0,
    last_msg_date  DATE DEFAULT CURRENT_DATE,
    total_messages BIGINT DEFAULT 0,
    is_admin       BOOLEAN DEFAULT FALSE,
    is_banned      BOOLEAN DEFAULT FALSE,
    language_code  TEXT DEFAULT 'ru'
);

CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,               -- user | assistant
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_user_id ON conversations(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS payments (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    charge_id       TEXT UNIQUE NOT NULL,    -- telegram_payment_charge_id
    payload         TEXT NOT NULL,           -- pro_month | pro_3month | vip_month
    amount          INT NOT NULL,            -- в Stars
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    refunded        BOOLEAN DEFAULT FALSE,
    refund_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stats (
    date          DATE PRIMARY KEY DEFAULT CURRENT_DATE,
    new_users     INT DEFAULT 0,
    messages_sent INT DEFAULT 0,
    payments_cnt  INT DEFAULT 0,
    stars_earned  INT DEFAULT 0
);
"""


async def init_db(database_url: str) -> bool:
    """Инициализация пула и создание таблиц. Возвращает True если успешно."""
    global _pool
    if not database_url:
        logger.warning("DATABASE_URL не задан, работаю в in-memory режиме (данные не сохраняются).")
        return False
    if not ASYNCPG_AVAILABLE:
        logger.warning("asyncpg не установлен, работаю в in-memory режиме.")
        return False
    try:
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        async with _pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        logger.info("✅ PostgreSQL подключён, таблицы готовы.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        _pool = None
        return False


async def close_db():
    global _pool
    if _pool:
        await _pool.close()


# ─── In-memory fallback ──────────────────────────────────────────────────────

_mem_users: dict = {}
_mem_convs: dict = {}
_mem_payments: dict = {}


def _now():
    return datetime.utcnow()


# ─── Пользователи ────────────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str = "", first_name: str = "",
                             last_name: str = "", language_code: str = "ru") -> dict:
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            if not row:
                row = await conn.fetchrow(
                    """INSERT INTO users (user_id, username, first_name, last_name, language_code)
                    VALUES ($1,$2,$3,$4,$5) RETURNING *""",
                    user_id, username, first_name, last_name, language_code
                )
                # Статистика новых пользователей
                await conn.execute(
                    """INSERT INTO stats (date, new_users) VALUES (CURRENT_DATE, 1)
                    ON CONFLICT (date) DO UPDATE SET new_users = stats.new_users + 1"""
                )
            return dict(row)
    # In-memory
    if user_id not in _mem_users:
        _mem_users[user_id] = {
            "user_id": user_id, "username": username, "first_name": first_name,
            "last_name": last_name, "joined_at": _now(), "subscription": "free",
            "sub_expires": None, "messages_today": 0, "last_msg_date": _now().date(),
            "total_messages": 0, "is_admin": False, "is_banned": False,
        }
    return _mem_users[user_id]


async def get_user(user_id: int) -> Optional[dict]:
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            return dict(row) if row else None
    return _mem_users.get(user_id)


async def update_user_subscription(user_id: int, plan: str, days: int):
    expires = datetime.utcnow() + timedelta(days=days)
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET subscription=$1, sub_expires=$2 WHERE user_id=$3",
                plan, expires, user_id
            )
    elif user_id in _mem_users:
        _mem_users[user_id]["subscription"] = plan
        _mem_users[user_id]["sub_expires"] = expires


async def increment_message_count(user_id: int):
    """Увеличивает счётчик сообщений пользователя за день."""
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET
                    messages_today = CASE WHEN last_msg_date = CURRENT_DATE THEN messages_today + 1 ELSE 1 END,
                    last_msg_date = CURRENT_DATE,
                    total_messages = total_messages + 1
                WHERE user_id=$1
            """, user_id)
            await conn.execute(
                """INSERT INTO stats (date, messages_sent) VALUES (CURRENT_DATE, 1)
                ON CONFLICT (date) DO UPDATE SET messages_sent = stats.messages_sent + 1"""
            )
    elif user_id in _mem_users:
        u = _mem_users[user_id]
        today = _now().date()
        if u["last_msg_date"] != today:
            u["messages_today"] = 0
            u["last_msg_date"] = today
        u["messages_today"] += 1
        u["total_messages"] = u.get("total_messages", 0) + 1


async def get_messages_today(user_id: int) -> int:
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT messages_today, last_msg_date FROM users WHERE user_id=$1", user_id
            )
            if not row:
                return 0
            if row["last_msg_date"] < _now().date():
                return 0
            return row["messages_today"]
    u = _mem_users.get(user_id)
    if not u:
        return 0
    if u.get("last_msg_date") != _now().date():
        return 0
    return u.get("messages_today", 0)


async def set_admin(user_id: int, is_admin: bool = True):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_admin=$1 WHERE user_id=$2", is_admin, user_id)
    elif user_id in _mem_users:
        _mem_users[user_id]["is_admin"] = is_admin


async def ban_user(user_id: int, banned: bool = True):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_banned=$1 WHERE user_id=$2", banned, user_id)
    elif user_id in _mem_users:
        _mem_users[user_id]["is_banned"] = banned


# ─── История диалогов ────────────────────────────────────────────────────────

async def save_message(user_id: int, role: str, content: str):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO conversations (user_id, role, content) VALUES ($1,$2,$3)",
                user_id, role, content
            )
    else:
        if user_id not in _mem_convs:
            _mem_convs[user_id] = []
        _mem_convs[user_id].append({"role": role, "content": content})


async def get_history(user_id: int, limit: int = 20) -> list[dict]:
    if _pool:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content FROM conversations
                WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2""",
                user_id, limit
            )
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    msgs = _mem_convs.get(user_id, [])
    return msgs[-limit:]


async def clear_history(user_id: int):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute("DELETE FROM conversations WHERE user_id=$1", user_id)
    else:
        _mem_convs[user_id] = []


# ─── Платежи ─────────────────────────────────────────────────────────────────

async def save_payment(user_id: int, charge_id: str, payload: str, amount: int):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO payments (user_id, charge_id, payload, amount) VALUES ($1,$2,$3,$4)
                ON CONFLICT (charge_id) DO NOTHING""",
                user_id, charge_id, payload, amount
            )
            await conn.execute(
                """INSERT INTO stats (date, payments_cnt, stars_earned) VALUES (CURRENT_DATE,1,$1)
                ON CONFLICT (date) DO UPDATE SET
                    payments_cnt = stats.payments_cnt + 1,
                    stars_earned = stats.stars_earned + $1""",
                amount
            )
    else:
        _mem_payments[charge_id] = {
            "user_id": user_id, "payload": payload, "amount": amount, "created_at": _now()
        }


async def mark_refunded(charge_id: str):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET refunded=TRUE, refund_at=NOW() WHERE charge_id=$1", charge_id
            )
    elif charge_id in _mem_payments:
        _mem_payments[charge_id]["refunded"] = True


# ─── Статистика (для /admin) ──────────────────────────────────────────────────

async def get_stats() -> dict:
    if _pool:
        async with _pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            pro_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE subscription != 'free' AND (sub_expires IS NULL OR sub_expires > NOW())"
            )
            today_stats = await conn.fetchrow(
                "SELECT * FROM stats WHERE date = CURRENT_DATE"
            )
            return {
                "total_users": total_users or 0,
                "pro_users": pro_users or 0,
                "today_new": today_stats["new_users"] if today_stats else 0,
                "today_msgs": today_stats["messages_sent"] if today_stats else 0,
                "today_pays": today_stats["payments_cnt"] if today_stats else 0,
                "today_stars": today_stats["stars_earned"] if today_stats else 0,
            }
    return {
        "total_users": len(_mem_users),
        "pro_users": sum(1 for u in _mem_users.values() if u.get("subscription") != "free"),
        "today_new": 0, "today_msgs": 0, "today_pays": 0, "today_stars": 0,
    }


# ─── Aliases (совместимость с handlers) ──────────────────────────────────────

async def get_user_stats(user_id: int) -> dict:
    """Статистика пользователя: сообщения сегодня и всего."""
    count = await get_messages_today(user_id)
    total = _mem_users.get(user_id, {}).get("total_messages", 0)
    return {"today_messages": count, "total_messages": total}


async def get_dialog_history(user_id: int, limit: int = 20) -> list:
    return await get_history(user_id, limit=limit)


async def increment_daily_messages(user_id: int):
    return await increment_message_count(user_id)


async def reset_dialog_history(user_id: int):
    return await clear_history(user_id)


async def get_admin_stats() -> dict:
    return await get_stats()


async def get_all_user_ids() -> list:
    if _pool:
        async with _pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [r["user_id"] for r in rows]
    return list(_mem_users.keys())
