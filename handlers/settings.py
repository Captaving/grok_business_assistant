from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards import history_length_kb, language_kb, delay_kb, main_menu_kb
from database import get_user_settings, update_user_setting

router = Router()

@router.callback_query(F.data == "change_history")
async def change_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    
    await callback.message.edit_text(
        f"📜 **Длина истории диалога**\n\n"
        f"Сейчас: **{settings['history_length']}** сообщений\n\n"
        "Чем больше — тем лучше контекст, но тем дороже запросы к Grok.",
        reply_markup=history_length_kb(settings['history_length'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_history_"))
async def set_history_length(callback: CallbackQuery):
    length = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    await update_user_setting(user_id, "history_length", length)
    
    await callback.message.edit_text(
        f"✅ Длина истории изменена на **{length}** сообщений.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "change_language")
async def change_language(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    
    await callback.message.edit_text(
        f"🌐 **Язык ответов ассистента**\n\nТекущий: **{settings['language']}**",
        reply_markup=language_kb(settings['language'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    
    await update_user_setting(user_id, "language", lang)
    
    lang_names = {"ru": "Русский", "en": "English", "uk": "Українська", "es": "Español"}
    await callback.message.edit_text(
        f"✅ Язык ответов изменён на **{lang_names.get(lang, lang)}**.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "change_delay")
async def change_delay(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    
    await callback.message.edit_text(
        f"⏱ **Задержка перед ответом**\n\n"
        f"Сейчас: **{settings['response_delay']}** секунд\n\n"
        "Задержка делает ответы более естественными (как будто пишет человек).",
        reply_markup=delay_kb(settings['response_delay'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_delay_"))
async def set_delay(callback: CallbackQuery):
    delay = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    await update_user_setting(user_id, "response_delay", delay)
    
    await callback.message.edit_text(
        f"✅ Задержка ответа установлена на **{delay}** секунд.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()