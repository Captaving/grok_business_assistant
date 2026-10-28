import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from config import settings
from services import groq
from services.tasks import TaskDraft

log = logging.getLogger(__name__)

# Бесплатный тариф Groq пускает ~8000 токенов в минуту на модель (вместе с ответом),
# поэтому длинную расшифровку режем на куски и сводим в несколько заходов.
CHUNK_CHARS = 6000
MAX_ROUNDS = 3

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SUMMARY_PROMPT = """Ты — личный ассистент сотрудника. Тебе дают расшифровку голосовых и текстовых сообщений, \
которые руководитель прислал сотруднику (или заметки по ним). Разбери их для сотрудника.

Правила:
- Пиши по-русски, коротко и по делу, обращайся к сотруднику на «ты».
- Ничего не выдумывай: только то, что есть в сообщениях.
- Если руководитель передумал или поправил себя — оставь итоговый вариант и допиши «(уточнено)».
- Относительные сроки («завтра», «к пятнице») переведи в даты по текущей дате.
- Объединяй повторы одной и той же задачи.
- Без Markdown.

Ответь строго одним JSON-объектом такого вида:
{
  "brief": "суть всех сообщений в 1–2 предложениях",
  "tasks": [
    {
      "title": "короткая формулировка задачи, до 80 символов, начинается с глагола",
      "details": "подробности: что именно, кому, где, нюансы и пожелания руководителя",
      "quote": "короткая дословная цитата руководителя, из которой следует задача",
      "deadline": "срок для чтения, например «31.10, пятница (сказала „к пятнице“)», или пустая строка",
      "deadline_date": "срок в формате ГГГГ-ММ-ДД или пустая строка",
      "urgent": true или false — подчеркнул ли руководитель срочность
    }
  ],
  "questions": ["что неясно или противоречиво — стоит уточнить у руководителя"],
  "notes": ["важные факты, цифры и контекст, которые не являются задачами"]
}
Если задач нет — верни пустой список tasks."""

NOTES_PROMPT = """Это фрагмент расшифровки сообщений руководителя сотруднику. Выпиши из него кратко, \
но без потерь: все поручения (что, кому, сроки), договорённости, вопросы, важные факты и цифры. \
Сохраняй время сообщений в квадратных скобках и дословные формулировки поручений. \
Если руководитель меняет ранее данное поручение — так и укажи. Ничего не выдумывай. Без Markdown, только обычный текст."""


@dataclass
class Summary:
    brief: str = ""
    tasks: list[TaskDraft] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: str = ""  # если модель ответила не JSON — показываем как есть


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


def _str(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value) -> list[str]:
    return [s.strip() for s in value if isinstance(s, str) and s.strip()] if isinstance(value, list) else []


def _date(value) -> date | None:
    try:
        return date.fromisoformat(_str(value))
    except ValueError:
        return None


def parse_summary(content: str) -> Summary:
    start, end = content.find("{"), content.rfind("}")
    try:
        data = json.loads(content[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("не объект")
    except ValueError:
        log.warning("Модель ответила не JSON, показываю как есть")
        return Summary(raw=strip_markdown(content))

    tasks = []
    for item in data.get("tasks") or []:
        if not isinstance(item, dict) or not _str(item.get("title")):
            continue
        tasks.append(
            TaskDraft(
                title=_str(item.get("title")),
                details=_str(item.get("details")),
                quote=_str(item.get("quote")),
                deadline=_str(item.get("deadline")),
                deadline_date=_date(item.get("deadline_date")),
                urgent=item.get("urgent") is True,
            )
        )
    return Summary(
        brief=_str(data.get("brief")),
        tasks=tasks,
        questions=_strings(data.get("questions")),
        notes=_strings(data.get("notes")),
    )


def render_summary(summary: Summary) -> str:
    if summary.raw:
        return summary.raw
    parts = []
    if summary.brief:
        parts.append(f"🧾 Коротко: {summary.brief}")
    if summary.tasks:
        lines = ["✅ Задачи:"]
        for i, task in enumerate(summary.tasks, 1):
            line = f"{i}. {task.title}"
            if task.deadline:
                line += f" ⏰ {task.deadline}"
            if task.urgent:
                line += " ❗"
            lines.append(line)
        parts.append("\n".join(lines))
    else:
        parts.append("✅ Задач нет, только информация.")
    if summary.questions:
        parts.append("❓ Уточнить у руководителя:\n" + "\n".join(f"— {q}" for q in summary.questions))
    if summary.notes:
        parts.append("📌 Важно знать:\n" + "\n".join(f"— {n}" for n in summary.notes))
    return "\n\n".join(parts)


async def _chat(system: str, user: str, *, json_mode: bool = False) -> str:
    last_error: Exception | None = None
    for model in settings.LLM_MODELS:
        # JSON-режим Groq бывает капризным — при отказе повторяем тот же запрос без него
        for use_json in (True, False) if json_mode else (False,):
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.2,
                "max_completion_tokens": 3500,
            }
            if model.startswith("openai/gpt-oss"):
                payload["reasoning_effort"] = "low"
            if use_json:
                payload["response_format"] = {"type": "json_object"}
            try:
                result = await groq.request("/chat/completions", payload=payload)
            except groq.ModelUnavailable as e:
                log.warning("Модель %s недоступна, пробую следующую: %s", model, e)
                last_error = e
                break
            except groq.GroqError as e:
                if use_json and "json" in str(e).lower():
                    log.warning("JSON-режим не сработал у %s, повторяю без него: %s", model, e)
                    last_error = e
                    continue
                raise
            content = result["choices"][0]["message"].get("content") or ""
            if content.strip():
                return content
            last_error = groq.GroqError(f"модель {model} вернула пустой ответ")
            break
    raise last_error or groq.GroqError("не задана ни одна модель в LLM_MODELS")


async def summarize(transcript: str, sender: str, now: datetime) -> Summary:
    text = transcript
    for _ in range(MAX_ROUNDS):
        if len(text) <= CHUNK_CHARS:
            break
        parts = split_text(text, CHUNK_CHARS)
        log.info("Расшифровка длинная (%s символов), свожу по частям: %s", len(text), len(parts))
        notes = [
            strip_markdown(await _chat(NOTES_PROMPT, f"Часть {i} из {len(parts)}.\n\n{part}"))
            for i, part in enumerate(parts, 1)
        ]
        text = "\n\n".join(notes)
    else:
        text = text[:CHUNK_CHARS]

    header = f"Сейчас: {WEEKDAYS[now.weekday()]}, {now:%d.%m.%Y %H:%M}.\nОтправитель: {sender}.\n\nСообщения:\n"
    return parse_summary(await _chat(SUMMARY_PROMPT, header + text, json_mode=True))
