import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from config import settings
from services.batcher import Batch, Batcher
from services.groq_stt import transcribe
from services.summarizer import render_summary, split_text, summarize
from services.task_views import card_text, proposal_kb
from services.tasks import TaskDraft, TaskStore

log = logging.getLogger(__name__)

TG_LIMIT = 4000
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024  # больше бот скачать не может
AUDIO_EXT = {
    "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/ogg": "ogg", "audio/opus": "ogg",
    "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/m4a": "m4a", "audio/aac": "m4a",
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/flac": "flac", "audio/webm": "webm",
}


def local(dt: datetime) -> datetime:
    return dt.astimezone(settings.TIMEZONE)


async def notify(bot: Bot, text: str, reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None) -> None:
    """Пишет владельцу. Больше бот не пишет никому. Кнопки цепляются к последней части."""
    parts = split_text(text, TG_LIMIT) or [text]
    for i, part in enumerate(parts):
        try:
            await bot.send_message(settings.OWNER_ID, part, reply_markup=reply_markup if i == len(parts) - 1 else None)
        except TelegramAPIError as e:
            log.warning("Не могу написать владельцу (он нажал /start у бота?): %s", e)
            return


async def send_proposals(bot: Bot, store: TaskStore, drafts: list[TaskDraft], source: str) -> None:
    """Каждую найденную задачу — отдельным сообщением с вопросом «Добавить?»."""
    for i, draft in enumerate(drafts, 1):
        task = store.add(draft, source)
        head = f"🆕 Задача {i} из {len(drafts)}" if len(drafts) > 1 else "🆕 Новая задача"
        await notify(bot, f"{head}\n\n{card_text(task)}\n\nДобавить в задачи?", reply_markup=proposal_kb(task))


def _media(message: Message):
    """(файл, имя для Groq) для голосового/кружка/аудио, иначе None."""
    if message.voice:
        return message.voice, "voice.ogg"
    if message.video_note:
        return message.video_note, "video_note.mp4"
    if message.audio:
        ext = AUDIO_EXT.get(message.audio.mime_type or "")
        if not ext and message.audio.file_name and "." in message.audio.file_name:
            ext = message.audio.file_name.rsplit(".", 1)[1].lower()
        return message.audio, f"audio.{ext or 'mp3'}"
    return None


async def _download_and_transcribe(bot: Bot, file, filename: str) -> str:
    if (file.file_size or 0) > TG_DOWNLOAD_LIMIT:
        return "[файл больше 20 МБ — Telegram не даёт боту его скачать]"
    buffer = await bot.download(file, timeout=120)
    return await transcribe(buffer.read(), filename)


def collect(batcher: Batcher, bot: Bot, message: Message, *, key, title, sender, delay, require_media) -> bool:
    """Кладёт сообщение в пачку. Возвращает True, если с него началась новая пачка."""
    is_new = False
    media = _media(message)
    if media:
        file, filename = media
        is_new |= batcher.add_media(
            key, title, sender, message.date, _download_and_transcribe(bot, file, filename),
            delay=delay, require_media=require_media,
        )
    text = message.text or message.caption
    if text:
        is_new |= batcher.add_text(key, title, sender, message.date, text, delay=delay, require_media=require_media)
    return is_new


def make_processor(bot: Bot, store: TaskStore):
    async def process(batch: Batch) -> None:
        lines, voices, texts, failed = [], 0, 0, 0
        for entry in batch.entries:
            if entry.is_media:
                voices += 1
                try:
                    text = await entry.task
                except Exception as e:
                    log.warning("Не удалось расшифровать голосовое: %s", e)
                    text = ""
                if not text:
                    failed += 1
                    text = "[не удалось распознать]"
                icon = "🎤"
            else:
                texts += 1
                text, icon = entry.text, "💬"
            lines.append(f"[{local(entry.time):%H:%M}] {icon} {entry.sender}: {text}")
        transcript = "\n".join(lines)

        start, end = local(batch.entries[0].time), local(batch.entries[-1].time)
        counts = ", ".join(p for p in (f"{voices} 🎤" if voices else "", f"{texts} 💬" if texts else "") if p)
        header = f"📋 {batch.title} · {start:%d.%m} {start:%H:%M}–{end:%H:%M} · {counts}"
        if failed:
            header += f"\n⚠️ Не распознано: {failed}"

        senders = {e.sender for e in batch.entries}
        source = senders.pop() if len(senders) == 1 else batch.title

        summary = None
        try:
            summary = await summarize(transcript, source, datetime.now(settings.TIMEZONE))
            text = render_summary(summary)
        except Exception as e:
            log.exception("Не удалось сделать сводку")
            text = f"⚠️ Не получилось сделать сводку: {e}\nПолная расшифровка — в файле ниже."

        await notify(bot, f"{header}\n\n{text}")

        if settings.SEND_TRANSCRIPT or summary is None:
            try:
                await bot.send_document(
                    settings.OWNER_ID,
                    BufferedInputFile(transcript.encode("utf-8"), filename=f"transcript_{end:%Y-%m-%d_%H-%M}.txt"),
                    caption="📎 Полная расшифровка",
                )
            except TelegramAPIError as e:
                log.warning("Не удалось отправить расшифровку: %s", e)

        if summary and summary.tasks:
            await send_proposals(bot, store, summary.tasks, source=source)

    return process
