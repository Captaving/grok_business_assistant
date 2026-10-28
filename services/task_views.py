from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import settings
from services.tasks import Task, TaskDraft, TaskStore

TASKS_BUTTON = "📋 Задачи"
MAIN_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=TASKS_BUTTON)]], resize_keyboard=True, is_persistent=True)
PAGE_SIZE = 8

# код -> подпись кнопки
REMIND_OPTIONS = {
    "1h": "⏱ Через 1 час",
    "3h": "⏱ Через 3 часа",
    "tm": "🌅 Завтра в 9:00",
    "3d": "📅 Через 3 дня в 9:00",
}


def cb(action: str, task_id: int = 0, arg: str | int = "") -> str:
    return f"t:{action}:{task_id}:{arg}"


def parse_cb(data: str) -> tuple[str, int, str]:
    _, action, task_id, arg = (data.split(":", 3) + ["", "", ""])[:4]
    return action, int(task_id or 0), arg


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def now_local() -> datetime:
    return datetime.now(settings.TIMEZONE)


def fmt_ts(ts: int) -> str:
    return f"{datetime.fromtimestamp(ts, settings.TIMEZONE):%d.%m %H:%M}"


def is_overdue(task: Task, today: date | None = None) -> bool:
    return bool(task.deadline_date and task.deadline_date < (today or now_local().date()))


def remind_at(code: str, now: datetime) -> int | None:
    morning = dict(hour=9, minute=0, second=0, microsecond=0)
    if code == "1h":
        moment = now + timedelta(hours=1)
    elif code == "3h":
        moment = now + timedelta(hours=3)
    elif code == "tm":
        moment = (now + timedelta(days=1)).replace(**morning)
    elif code == "3d":
        moment = (now + timedelta(days=3)).replace(**morning)
    else:
        return None
    return int(moment.timestamp())


def draft_from_text(text: str) -> TaskDraft:
    """Задача из того, что владелец написал сам: первая строка — заголовок, весь текст — подробности."""
    text = text.strip()
    first = text.splitlines()[0]
    if text == first and len(text) <= 80:
        return TaskDraft(title=text)
    return TaskDraft(title=first if len(first) <= 80 else first[:79] + "…", details=text)


# --- Тексты ---

def card_text(task: Task) -> str:
    lines = [f"📌 {task.title}"]
    if task.details:
        lines.append(f"\n{task.details}")
    if task.quote:
        lines.append(f"\n💬 «{task.quote}»")
    lines.append("")
    if task.deadline:
        lines.append(f"⏰ Срок: {task.deadline}" + (" — 🔥 просрочено" if task.status == "open" and is_overdue(task) else ""))
    if task.urgent:
        lines.append("❗ Срочно")
    lines.append(f"👤 От: {task.source}, {fmt_ts(task.created_at)}")
    if task.status == "open" and task.remind_at:
        lines.append(f"🔔 Напомню: {fmt_ts(task.remind_at)}")
    if task.status == "done" and task.closed_at:
        lines.append(f"✅ Закрыта: {fmt_ts(task.closed_at)}")
    return "\n".join(lines).strip()


def task_label(task: Task) -> str:
    marks = ("🔥" if is_overdue(task) else "") + ("❗" if task.urgent else "") + ("🔔" if task.remind_at else "")
    label = f"{marks} {task.title}".strip()
    if task.deadline_date:
        label += f" · {task.deadline_date:%d.%m}"
    return label if len(label) <= 60 else label[:57] + "…"


# --- Клавиатуры ---

def list_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📋 Открыть список", cb("list"))]])


def proposal_kb(task: Task) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("✅ Да", cb("yes", task.id)), _btn("❌ Нет", cb("no", task.id))]])


def card_kb(task: Task) -> InlineKeyboardMarkup:
    if task.status == "open":
        rows = [
            [_btn("✅ Закрыть", cb("done", task.id)), _btn("⏰ Напомнить", cb("rem", task.id))],
            [_btn("📋 Все задачи", cb("list"))],
        ]
    else:
        rows = [[_btn("↩️ Вернуть в работу", cb("reopen", task.id)), _btn("📋 Все задачи", cb("list"))]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def remind_kb(task: Task) -> InlineKeyboardMarkup:
    codes = list(REMIND_OPTIONS)
    rows = [
        [_btn(REMIND_OPTIONS[c], cb("rset", task.id, c)) for c in codes[i : i + 2]]
        for i in range(0, len(codes), 2)
    ]
    if task.remind_at:
        rows.append([_btn("🔕 Не напоминать", cb("rset", task.id, "off"))])
    rows.append([_btn("← Назад", cb("card", task.id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def list_view(store: TaskStore, page: int = 0) -> tuple[str, InlineKeyboardMarkup | None]:
    tasks, total = store.list_open(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    if not total:
        return "🎉 Открытых задач нет.", None
    if not tasks and page > 0:  # страница опустела после закрытия задач
        return list_view(store, 0)
    rows = [[_btn(task_label(t), cb("card", t.id))] for t in tasks]
    nav = []
    if page > 0:
        nav.append(_btn("◀️", cb("list", 0, page - 1)))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(_btn("▶️", cb("list", 0, page + 1)))
    if nav:
        rows.append(nav)
    pages = f" (стр. {page + 1})" if total > PAGE_SIZE else ""
    return f"📋 Открытые задачи: {total}{pages}\nНажми на задачу, чтобы открыть.", InlineKeyboardMarkup(inline_keyboard=rows)


def closed_view(store: TaskStore) -> tuple[str, InlineKeyboardMarkup | None]:
    tasks = store.list_closed()
    if not tasks:
        return "Закрытых задач пока нет.", None
    rows = [[_btn(f"✅ {t.title}"[:57] + f" · {fmt_ts(t.closed_at)[:5]}", cb("card", t.id))] for t in tasks]
    return "✅ Недавно закрытые (нажми, чтобы вернуть в работу):", InlineKeyboardMarkup(inline_keyboard=rows)


def digest_text(store: TaskStore, today: date) -> str | None:
    tasks, total = store.list_open()
    if not total:
        return None
    overdue = [t for t in tasks if t.deadline_date and t.deadline_date < today]
    due_today = [t for t in tasks if t.deadline_date == today]
    parts = [f"☀️ Доброе утро! Открытых задач: {total}"]
    if overdue:
        parts.append("🔥 Просрочено:\n" + "\n".join(f"— {t.title} (срок {t.deadline_date:%d.%m})" for t in overdue))
    if due_today:
        parts.append("📅 Срок сегодня:\n" + "\n".join(f"— {t.title}" for t in due_today))
    if not overdue and not due_today:
        parts.append("Горящих сроков нет 👌")
    return "\n\n".join(parts)
