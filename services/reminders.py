import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

from config import settings
from services.report import notify
from services.task_views import card_kb, card_text, digest_text, list_kb, now_local
from services.tasks import TaskStore

log = logging.getLogger(__name__)

TICK = 30  # секунд между проверками
DIGEST_WINDOW = timedelta(hours=3)  # если бот лежал утром — догоняем сводку, но не вечером


async def tick(bot: Bot, store: TaskStore, now: datetime) -> None:
    for task in store.due_reminders(int(now.timestamp())):
        task = store.set_reminder(task.id, None)
        await notify(bot, f"🔔 Напоминание!\n\n{card_text(task)}", reply_markup=card_kb(task))

    if settings.DIGEST_TIME is None:
        return
    hour, minute = settings.DIGEST_TIME
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    today = now.date().isoformat()
    if start <= now < start + DIGEST_WINDOW and store.get_meta("digest_date") != today:
        store.set_meta("digest_date", today)
        text = digest_text(store, now.date())
        if text:
            await notify(bot, text, reply_markup=list_kb())


async def run(bot: Bot, store: TaskStore) -> None:
    while True:
        try:
            await tick(bot, store, now_local())
        except Exception:
            log.exception("Ошибка в планировщике напоминаний")
        await asyncio.sleep(TICK)
