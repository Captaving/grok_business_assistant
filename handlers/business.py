from aiogram import Router
from aiogram.types import Message
from database import (
    get_user_settings, 
    get_chat_history, 
    add_message_to_history,
)
from services.grok import generate_response
import asyncio
from aiogram import Bot

router = Router()

@router.business_message()
async def handle_business_message(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    
    business_conn_id = message.business_connection_id
    client_chat_id = message.chat.id

    # Получаем владельца через API (не из message.from_user!)
    try:
        connection = await bot.get_business_connection(business_conn_id)
        owner_user_id = connection.user.id
    except Exception as e:
        print(f"[BUSINESS] Не удалось получить connection: {e}")
        return

    settings = await get_user_settings(owner_user_id)
    
    if not settings.get("custom_prompt"):
        print(f"[BUSINESS] Нет промта для owner_user_id={owner_user_id}")
        return
    
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
    
    await add_message_to_history(business_conn_id, client_chat_id, "user", user_text)
    
    response_text = await generate_response(
        system_prompt=settings["custom_prompt"],
        chat_history=history,
        user_message=user_text,
        language=settings["language"]
    )
    
    await add_message_to_history(business_conn_id, client_chat_id, "assistant", response_text)
    
    if settings.get("response_delay", 0) > 0:
        await asyncio.sleep(settings["response_delay"])
    
    try:
        await bot.send_message(
            chat_id=client_chat_id,
            text=response_text,
            business_connection_id=business_conn_id
        )
    except Exception as e:
        print(f"[BUSINESS SEND ERROR] {e}")