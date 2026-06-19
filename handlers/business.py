from aiogram import Router, F
from aiogram.types import Message
from database import (
    get_user_settings, 
    get_chat_history, 
    add_message_to_history,
    clear_chat_history
)
from services.grok import generate_response
import asyncio
from aiogram import Bot

router = Router()

@router.business_message()
async def handle_business_message(message: Message, bot: Bot):
    """
    Обработка сообщений, которые приходят через подключённый Business-бот.
    """
    if not message.business_connection_id:
        return
    
    business_conn_id = message.business_connection_id
    client_chat_id = message.chat.id
    
    # Получаем настройки владельца бизнес-аккаунта
    # В business_message message.from_user — это владелец аккаунта!
    owner_user_id = message.from_user.id if message.from_user else None
    
    if not owner_user_id:
        return
    
    settings = await get_user_settings(owner_user_id)
    
    if not settings["custom_prompt"]:
        # Если промт не установлен — не отвечаем
        return
    
    # Получаем историю диалога с этим клиентом
    history = await get_chat_history(
        business_conn_id, 
        client_chat_id, 
        limit=settings["history_length"]
    )
    
    user_text = message.text or ""
    
    # Если голосовое — здесь можно добавить транскрипцию (пока пропускаем для простоты)
    if message.voice:
        user_text = "[Голосовое сообщение — транскрипция будет позже]"
    
    if not user_text:
        return
    
    # Добавляем сообщение клиента в историю
    await add_message_to_history(business_conn_id, client_chat_id, "user", user_text)
    
    # Генерируем ответ Grok
    response_text = await generate_response(
        system_prompt=settings["custom_prompt"],
        chat_history=history,
        user_message=user_text,
        language=settings["language"]
    )
    
    # Добавляем ответ ассистента в историю
    await add_message_to_history(business_conn_id, client_chat_id, "assistant", response_text)
    
    # Задержка (чтобы выглядело естественно)
    if settings["response_delay"] > 0:
        await asyncio.sleep(settings["response_delay"])
    
    # Отправляем ответ от имени владельца бизнес-аккаунта
    try:
        await bot.send_message(
            chat_id=client_chat_id,
            text=response_text,
            business_connection_id=business_conn_id
        )
    except Exception as e:
        print(f"[BUSINESS SEND ERROR] {e}")