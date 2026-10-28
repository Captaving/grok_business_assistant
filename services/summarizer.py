import logging
import re
from datetime import datetime

from config import settings
from services import groq

log = logging.getLogger(__name__)

# Бесплатный тариф Groq пускает ~8000 токенов в минуту на модель,
# поэтому длинную расшифровку режем на куски и сводим в несколько заходов.
CHUNK_CHARS = 7000
MAX_ROUNDS = 3

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SUMMARY_PROMPT = """Ты — личный ассистент сотрудника. Тебе дают расшифровку голосовых и текстовых сообщений, \
которые руководитель прислал сотруднику (или заметки по ним). Составь для сотрудника понятную сводку.

Правила:
- Пиши по-русски, коротко и по делу, обращайся к сотруднику на «ты».
- Ничего не выдумывай: только то, что есть в сообщениях.
- Если руководитель передумал или поправил себя — оставь итоговый вариант и пометь «(уточнено)».
- Относительные сроки («завтра», «к пятнице») переведи в даты по текущей дате, исходную формулировку оставь в скобках.
- Объединяй повторы одной и той же задачи.
- Без Markdown: никаких **, #, таблиц. Только обычный текст, эмодзи и нумерованные списки.

Формат ответа:
🧾 Коротко: 1–2 предложения о сути.

✅ Задачи:
1. Что сделать — детали (что, кому, где). ⏰ срок, если назван. ❗ если руководитель подчеркнул срочность.

❓ Уточнить у руководителя:
— неясные моменты, противоречия, недосказанности.

📌 Важно знать:
— факты, цифры и контекст, которые не являются задачами.

Разделы «Уточнить» и «Важно знать» выводи, только если в них есть что написать.
Если задач нет — напиши в разделе «Задачи»: «Задач нет, только информация»."""

NOTES_PROMPT = """Это фрагмент расшифровки сообщений руководителя сотруднику. Выпиши из него кратко, \
но без потерь: все поручения (что, кому, сроки), договорённости, вопросы, важные факты и цифры. \
Сохраняй время сообщений в квадратных скобках. Если руководитель меняет ранее данное поручение — так и укажи. \
Ничего не выдумывай. Без Markdown, только обычный текст."""


def split_text(text: str, limit: int) -> list[str]:
    """Режет текст по строкам на куски не длиннее limit (слишком длинную строку — как придётся)."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return chunks


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("```", "")
    return text.strip()


async def _chat(system: str, user: str) -> str:
    last_error: Exception | None = None
    for model in settings.LLM_MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_completion_tokens": 2500,
        }
        if model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"
        try:
            result = await groq.request("/chat/completions", payload=payload)
        except groq.ModelUnavailable as e:
            log.warning("Модель %s недоступна, пробую следующую: %s", model, e)
            last_error = e
            continue
        content = result["choices"][0]["message"].get("content") or ""
        if content.strip():
            return strip_markdown(content)
        last_error = groq.GroqError(f"модель {model} вернула пустой ответ")
    raise last_error or groq.GroqError("не задана ни одна модель в LLM_MODELS")


async def summarize(transcript: str, sender: str, now: datetime) -> str:
    text = transcript
    for _ in range(MAX_ROUNDS):
        if len(text) <= CHUNK_CHARS:
            break
        parts = split_text(text, CHUNK_CHARS)
        log.info("Расшифровка длинная (%s символов), свожу по частям: %s", len(text), len(parts))
        notes = [
            await _chat(NOTES_PROMPT, f"Часть {i} из {len(parts)}.\n\n{part}")
            for i, part in enumerate(parts, 1)
        ]
        text = "\n\n".join(notes)
    else:
        text = text[:CHUNK_CHARS]

    header = f"Сейчас: {WEEKDAYS[now.weekday()]}, {now:%d.%m.%Y %H:%M}.\nОтправитель: {sender}.\n\nСообщения:\n"
    return await _chat(SUMMARY_PROMPT, header + text)
