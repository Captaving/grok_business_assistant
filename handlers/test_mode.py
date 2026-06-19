from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import test_mode_kb, main_menu_kb
from database import get_user_settings, get_chat_history, add_message_to_history, clear_chat_history
from services.grok import generate_response
import asyncio

router = Router()

class TestStates(StatesGroup):
    chatting = State()

TEST_CHAT_ID = -999999  # специальный ID для тестового чата

@router.callback_query(F.data == "test_mode")
async def start_test_mode(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    
    if not settings["custom_prompt"]:
        await callback.message.edit_text(
            "❌ Сначала установи промт!",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return
    
    await state.set_state(TestStates.chatting)
    await state.update_data(test_user_id=user_id)
    
    text = (
        "🧪 **Тестовый режим включён**\n\n"
        "Пиши сообщения, как будто ты — клиент. Я буду отвечать по твоему текущему промту.\n\n"
        "Чтобы выйти — нажми кнопку ниже или напиши /cancel"
    )
    await callback.message.edit_text(text, reply_markup=test_mode_kb())
    await callback.answer()

@router.message(TestStates.chatting)
async def handle_test_message(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Тестовый режим выключен.", reply_markup=main_menu_kb())
            return
    
    user_id = message.from_user.id
    settings = await get_user_settings(user_id)
    
    # Получаем историю тестового чата
    history = await get_chat_history("TEST", TEST_CHAT_ID, limit=settings["history_length"])
    
    # Добавляем сообщение пользователя
    await add_message_to_history("TEST", TEST_CHAT_ID, "user", message.text or "[голосовое]")
    
    # Генерируем ответ
    response = await generate_response(
        system_prompt=settings["custom_prompt"],
        chat_history=history,
        user_message=message.text or "[голосовое сообщение]",
        language=settings["language"]
    )
    
    # Сохраняем ответ ассистента
    await add_message_to_history("TEST", TEST_CHAT_ID, "assistant", response)
    
    # Имитируем задержку
    if settings["response_delay"] > 0:
        await asyncio.sleep(settings["response_delay"])
    
    await message.answer(response)

@router.callback_query(F.data == "reset_test_chat")
async def reset_test_chat(callback: CallbackQuery, state: FSMContext):
    await clear_chat_history("TEST", TEST_CHAT_ID)
    await callback.message.edit_text(
        "🔄 Тестовый чат сброшен. Можешь начать заново.",
        reply_markup=test_mode_kb()
    )
    await callback.answer()