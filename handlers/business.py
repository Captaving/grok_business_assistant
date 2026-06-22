from aiogram import Router
from aiogram.types import Message
from database import get_user_settings, get_chat_history, add_message_to_history
from services.grok import generate_response
import asyncio
from aiogram import Bot
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.business_message()
async def handle_business_message(message: Message, bot: Bot):
    if not message.business_connection_id:
        return

    try:
        # === ГЛАВНОЕ ИСПРАВЛЕНИЕ ===
        # Получаем владельца бизнес-аккаунта через API
        business_conn = await bot.get_business_connection(message.business_connection_id)
        owner_user_id = business_conn.user.id
    except Exception as e:
        logger.error(f"Не удалось получить business_connection: {e}")
        return

    settings = await get_user_settings(owner_user_id)

    if not settings.get("custom_prompt"):
        logger.info(f"Промт не установлен для пользователя {owner_user_id}")
        # Здесь можно добавить отправку сообщения владельцу (опционально)
        return

    business_conn_id = message.business_connection_id
    client_chat_id = message.chat.id

    # Получаем историю
    history = await get_chat_history(
        business_conn_id, 
        client_chat_id, 
        limit=settings["history_length"]
    )

    user_text = message.text or ""
    if message.voice:
        user_text = "[Голосовое сообщение]"

    if not user_text:
        return

    # Сохраняем сообщение клиента
    await add_message_to_history(business_conn_id, client_chat_id, "user", user_text)

    # Генерируем ответ
    response_text = await generate_response(
        system_prompt=settings["custom_prompt"],
        chat_history=history,
        user_message=user_text,
        language=settings["language"]
    )

    # Сохраняем ответ
    await add_message_to_history(business_conn_id, client_chat_id, "assistant", response_text)

    # Задержка
    if settings.get("response_delay", 0) > 0:
        await asyncio.sleep(settings["response_delay"])

    # Отправляем ответ
    try:
        await bot.send_message(
            chat_id=client_chat_id,
            text=response_text,
            business_connection_id=business_conn_id
        )
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")