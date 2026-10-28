import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from services.task_views import (
    TASKS_BUTTON, card_kb, card_text, cb, closed_view, digest_text, draft_from_text, fmt_ts, list_kb, list_view,
    now_local, parse_cb, remind_at, remind_kb,
)
from services.tasks import TaskStore

log = logging.getLogger(__name__)
router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user.id == settings.OWNER_ID)
router.callback_query.filter(F.from_user.id == settings.OWNER_ID)


@router.message(F.text == TASKS_BUTTON)
@router.message(Command("tasks"))
async def show_tasks(message: Message, store: TaskStore):
    text, kb = list_view(store)
    await message.answer(text, reply_markup=kb)


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, store: TaskStore):
    if not command.args:
        await message.answer("Напиши задачу после команды, например:\n/add Позвонить Иванову насчёт договора")
        return
    task = store.add(draft_from_text(command.args), source="Ты", status="open")
    await message.answer(f"✅ Добавлено в задачи: {task.title}", reply_markup=card_kb(task))


@router.message(Command("today"))
async def cmd_today(message: Message, store: TaskStore):
    text = digest_text(store, now_local().date())
    if text is None:
        await message.answer("🎉 Открытых задач нет.")
        return
    await message.answer(text.replace("☀️ Доброе утро! ", "📅 "), reply_markup=list_kb())


@router.message(Command("closed"))
async def cmd_closed(message: Message, store: TaskStore):
    text, kb = closed_view(store)
    await message.answer(text, reply_markup=kb)


async def _show(callback: CallbackQuery, bot: Bot, text: str, kb: InlineKeyboardMarkup | None) -> None:
    """Перерисовывает сообщение с кнопками, а если не вышло (слишком старое) — шлёт новое."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
            log.warning("Не удалось отредактировать сообщение: %s", e)
    await bot.send_message(settings.OWNER_ID, text, reply_markup=kb)


@router.callback_query(F.data.startswith("t:"))
async def on_task_button(callback: CallbackQuery, bot: Bot, store: TaskStore):
    action, task_id, arg = parse_cb(callback.data)

    if action == "list":
        text, kb = list_view(store, int(arg or 0))
        await _show(callback, bot, text, kb)
        await callback.answer()
        return

    task = store.get(task_id)
    if task is None:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    toast = None
    if action == "yes":
        task = store.set_status(task.id, "open")
        text = f"✅ Добавлено в задачи: {task.title}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📄 Открыть", callback_data=cb("card", task.id)),
            InlineKeyboardButton(text="📋 Все задачи", callback_data=cb("list")),
        ]])
        toast = "Добавлено"
    elif action == "no":
        task = store.set_status(task.id, "rejected")
        text = f"❌ Не добавлено: {task.title}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Всё-таки добавить", callback_data=cb("yes", task.id)),
        ]])
    elif action == "card":
        text, kb = card_text(task), card_kb(task)
    elif action == "done":
        task = store.set_status(task.id, "done")
        text, kb = f"✅ Задача закрыта!\n\n{card_text(task)}", card_kb(task)
        toast = "✅ Задача закрыта"
    elif action == "reopen":
        task = store.set_status(task.id, "open")
        text, kb = card_text(task), card_kb(task)
        toast = "↩️ Задача снова в работе"
    elif action == "rem":
        if task.status != "open":
            await callback.answer("Задача уже закрыта", show_alert=True)
            return
        text, kb = f"{card_text(task)}\n\nКогда напомнить?", remind_kb(task)
    elif action == "rset":
        when = remind_at(arg, now_local())
        task = store.set_reminder(task.id, when)
        text, kb = card_text(task), card_kb(task)
        toast = f"🔔 Напомню {fmt_ts(when)}" if when else "🔕 Напоминание снято"
    else:
        await callback.answer()
        return

    await _show(callback, bot, text, kb)
    await callback.answer(toast)
