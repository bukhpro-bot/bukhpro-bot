"""
Обработчик входящих текстовых сообщений — ядро чат-интерфейса.
Отправляет запросы в Groq (Llama 3.3 70B) и возвращает ответ.
"""
import logging
import groq
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from config import Config
from database import (
    get_or_create_user, get_user_stats, get_dialog_history,
    save_message, increment_daily_messages,
)
from keyboards import quick_commands_keyboard
from states import AdminState, FeedbackState
from system_prompt import ACCOUNTING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()
REPLY_KB_TEXTS = {"📊 Меню", "❓ Помощь", "🔄 Сбросить диалог", "ℹ️ О боте"}

def _get_daily_limit(sub: str, config: Config) -> int:
    return config.messages_per_day

def _get_system_prompt(sub: str) -> str:
    return ACCOUNTING_SYSTEM_PROMPT

def _build_messages(history: list[dict], user_text: str, system_prompt: str) -> list[dict]:
    msgs = [{"role": "system", "content": system_prompt}]
    for entry in history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_text})
    return msgs

@router.message(F.text, ~F.text.startswith("/"))
async def handle_message(message: Message, config: Config, state: FSMContext):
    if message.text in REPLY_KB_TEXTS:
        return
    current_state = await state.get_state()
    if current_state == AdminState.waiting_broadcast:
        await _handle_broadcast(message, config, state)
        return
    user_id = message.from_user.id
    user_text = message.text.strip()
    if not user_text:
        return
    user = await get_or_create_user(
        user_id=user_id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
    )
    stats = await get_user_stats(user_id)
    msgs_used = stats.get("today_messages", 0)
    sub = user.get("subscription", "free")
    limit = _get_daily_limit(sub, config)
    if msgs_used >= limit:
        await message.answer(
            f"⚠️ Достигнут дневной лимит ({config.messages_per_day} сообщений). Приходите завтра! 🌅"
        )
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    history = await get_dialog_history(user_id, limit=config.context_history_length)
    system_prompt = _get_system_prompt(sub)
    messages_for_api = _build_messages(history, user_text, system_prompt)
    try:
        client = groq.AsyncGroq(api_key=config.groq_api_key)
        response = await client.chat.completions.create(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=messages_for_api,
        )
        answer = response.choices[0].message.content.strip()
    except groq.RateLimitError:
        logger.warning("Rate limit от Groq")
        await message.answer("⚠️ Временная перегрузка сервиса. Попробуйте через минуту.")
        return
    except groq.APIStatusError as e:
        logger.error(f"Groq API error: {e.status_code} — {e.message}")
        await message.answer("❌ Ошибка при обращении к AI. Попробуйте чуть позже.")
        return
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при вызове Groq: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        return
    await save_message(user_id, role="user", content=user_text)
    await save_message(user_id, role="assistant", content=answer)
    await increment_daily_messages(user_id)
    remaining = max(0, limit - (msgs_used + 1))
    footer = f"\n\n💬 <i>Осталось сегодня: {remaining}/{limit}</i>"
    full_text = answer + footer
    await _send_long_message(message, full_text)

async def _send_long_message(message: Message, text: str, chunk_size: int = 4000):
    if len(text) <= chunk_size:
        await message.answer(text)
        return
    parts = []
    while len(text) > chunk_size:
        split_at = text.rfind("\n\n", 0, chunk_size)
        if split_at == -1:
            split_at = text.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        parts.append(text)
    for part in parts:
        if part:
            await message.answer(part)

async def _handle_broadcast(message: Message, config: Config, state: FSMContext):
    if message.from_user.id not in config.admin_ids:
        await state.clear()
        return
    from database import get_all_user_ids
    await state.clear()
    broadcast_text = f"📣 <b>Сообщение от администратора:</b>\n\n{message.text}"
    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Отправляю {len(user_ids)} пользователям...")
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, broadcast_text)
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {sent}\nНе доставлено: {failed}"
    )
