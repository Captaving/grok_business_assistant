from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import prompt_kb, main_menu_kb, cancel_kb
from database import get_user_settings, update_user_prompt
from config import settings as app_settings

router = Router()

class PromptStates(StatesGroup):
    waiting_for_prompt = State()

@router.callback_query(F.data == "change_prompt")
async def change_prompt_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_settings = await get_user_settings(user_id)
    
    current = user_settings["custom_prompt"] or "Промт ещё не установлен."
    
    text = (
        f"✏️ **Изменение промта**\n\n"
        f"Текущий промт:\n_{current}_\n\n"
        f"Напиши новый промт (максимум {app_settings.MAX_PROMPT_LENGTH} символов).\n\n"
        "Пример хорошего промта:\n"
        "_Ты — опытный менеджер по продажам квартир. Отвечай вежливо, предлагай просмотры, "
        "уточняй бюджет и район. Не навязывайся._"
    )
    
    await callback.message.edit_text(text, reply_markup=cancel_kb())
    await state.set_state(PromptStates.waiting_for_prompt)
    await callback.answer()

@router.message(PromptStates.waiting_for_prompt)
async def process_new_prompt(message: Message, state: FSMContext):
    prompt = message.text.strip()
    
    if len(prompt) > app_settings.MAX_PROMPT_LENGTH:
        await message.answer(
            f"❌ Промт слишком длинный ({len(prompt)} символов). "
            f"Максимум — {app_settings.MAX_PROMPT_LENGTH}."
        )
        return
    
    if len(prompt) < 20:
        await message.answer("❌ Промт слишком короткий. Напиши более подробную инструкцию.")
        return
    
    success = await update_user_prompt(message.from_user.id, prompt)
    
    if success:
        await message.answer(
            "✅ Промт успешно сохранён!\n\n"
            f"_{prompt}_",
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer("❌ Не удалось сохранить промт. Попробуй ещё раз.")
    
    await state.clear()

@router.callback_query(F.data == "cancel_prompt")
async def cancel_prompt(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=main_menu_kb())
    await callback.answer()