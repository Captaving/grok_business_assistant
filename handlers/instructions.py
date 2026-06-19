from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards import instructions_kb, main_menu_kb

router = Router()

@router.callback_query(F.data == "instructions")
async def show_instructions(callback: CallbackQuery):
    text = (
       "📖 **Как подключить ассистента к своим личным чатам**\n\n"
        "1. Открой Telegram и зайди в Настройки (иконка шестерёнки внизу слева на мобильном).\n\n"
        "2. Открой Изменить Профиль.\n\n"
        "3. Пролистай вниз и найди раздел *Автоматизация чатов*.\n\n"
        "4. Вставь ссылку или введи юзернейм этого бота (@AssistQBot).\n\n"
        "5. Дай боту права на чтение и ответы в сообщениях.\n\n"
        "6. Готово! Теперь бот будет отвечать в твоих личных чатах по твоему промту.\n\n"
        "⚠️ Важно: бот отвечает только в тех чатах, которые ты разрешишь в настройках Business."
    )
    
    await callback.message.edit_text(text, reply_markup=instructions_kb())
    await callback.answer()

@router.callback_query(F.data == "get_assistant")
async def get_assistant(callback: CallbackQuery):
    text = (
        "🚀 **Как получить работающего ассистента**\n\n"
        "1. Нажми **«Изменить промт»** и напиши подробную инструкцию для ассистента.\n"
        "2. Настрой длину истории, язык и задержку ответов.\n"
        "3. Протестируй ассистента кнопкой **«🧪 Протестировать»**.\n"
        "4. Подключи бота через **Telegram для бизнеса** (см. инструкцию).\n\n"
        "После подключения бот начнёт отвечать клиентам от твоего имени."
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()
