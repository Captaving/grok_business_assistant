from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_kb
from database import get_user_settings

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    settings = await get_user_settings(user_id)
    
    welcome_text = (
        "👋 Привет! Я — **твой персональный Grok-ассистент**.\n\n"
        "Я могу работать в двух режимах:\n"
        "• В этом чате — для настройки\n"
        "• В твоих личных чатах с клиентами (через Telegram Business)\n\n"
        "Сначала настрой меня под себя, потом подключи к своим чатам."
    )
    
    if settings["custom_prompt"]:
        welcome_text += f"\n\nТвой текущий промт:\n_{settings['custom_prompt'][:150]}..._"
    
    await message.answer(welcome_text, reply_markup=main_menu_kb())

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    
    text = "Главное меню"
    if settings["custom_prompt"]:
        text += f"\n\nТекущий промт:\n_{settings['custom_prompt'][:120]}..._"
    
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()