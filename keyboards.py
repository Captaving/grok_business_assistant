from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Получить ассистента", callback_data="get_assistant")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить промт", callback_data="change_prompt"),
        InlineKeyboardButton(text="📜 Изменить историю", callback_data="change_history")
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Язык ответов", callback_data="change_language"),
        InlineKeyboardButton(text="⏱ Задержка ответов", callback_data="change_delay")
    )
    builder.row(
        InlineKeyboardButton(text="🧪 Протестировать ассистента", callback_data="test_mode")
    )
    builder.row(
        InlineKeyboardButton(text="📖 Инструкция по подключению", callback_data="instructions")
    )
    return builder.as_markup()

def prompt_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить промт", callback_data="save_prompt"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prompt")
    )
    return builder.as_markup()

def history_length_kb(current: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for length in [4, 6, 8, 10, 12]:
        text = f"{'✅ ' if length == current else ''}{length} сообщений"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"set_history_{length}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    return builder.as_markup()

def language_kb(current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    languages = [
        ("Русский", "ru"),
        ("English", "en"),
        ("Українська", "uk"),
        ("Español", "es")
    ]
    for name, code in languages:
        text = f"{'✅ ' if code == current else ''}{name}"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"set_lang_{code}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    return builder.as_markup()

def delay_kb(current: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for delay in [0, 2, 4, 6, 8, 12]:
        text = f"{'✅ ' if delay == current else ''}{delay} сек"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"set_delay_{delay}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    return builder.as_markup()

def instructions_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Открыть инструкцию", url="https://t.me/your_channel_or_post")  # замени на свою
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")
    )
    return builder.as_markup()

def test_mode_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить тестовый чат", callback_data="reset_test_chat")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")
    )
    return builder.as_markup()

def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()