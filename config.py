import os
import sys
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        sys.exit(f"Не задана переменная {name}. Запусти install.sh или заполни .env вручную (см. .env.example)")
    return value.strip()


def _int(name: str, default: str | None = None) -> int:
    raw = _env(name, default)
    try:
        return int(raw)
    except ValueError:
        sys.exit(f"{name} должно быть числом, а сейчас: {raw!r}")


def _zone(name: str, default: str) -> ZoneInfo:
    raw = _env(name, default)
    try:
        return ZoneInfo(raw)
    except Exception:
        sys.exit(f"{name}: неизвестный часовой пояс {raw!r}. Пример: Europe/Moscow")


def _clock(name: str, default: str) -> tuple[int, int] | None:
    raw = os.getenv(name, default).strip().lower()
    if raw in ("", "0", "off", "нет"):
        return None
    try:
        hour, minute = (int(x) for x in raw.split(":"))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute
    except ValueError:
        pass
    sys.exit(f"{name} должно быть временем вида 09:00 (или off), а сейчас: {raw!r}")


@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str
    OWNER_ID: int  # единственный человек, которому бот пишет и которого слушается
    GROQ_API_KEY: str
    GROQ_BASE_URL: str
    STT_MODEL: str
    STT_LANGUAGE: str
    LLM_MODELS: tuple[str, ...]  # первая — основная, остальные — запасные
    BATCH_DELAY: int  # сколько секунд тишины ждать, прежде чем делать сводку
    FORWARD_DELAY: int  # то же для пересланных боту сообщений
    TIMEZONE: ZoneInfo
    SEND_TRANSCRIPT: bool
    DB_PATH: str
    DIGEST_TIME: tuple[int, int] | None  # утренняя сводка по задачам, None — выключена


settings = Settings(
    BOT_TOKEN=_env("BOT_TOKEN"),
    OWNER_ID=_int("OWNER_ID"),
    GROQ_API_KEY=_env("GROQ_API_KEY"),
    GROQ_BASE_URL=_env("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
    STT_MODEL=_env("STT_MODEL", "whisper-large-v3"),
    STT_LANGUAGE=os.getenv("STT_LANGUAGE", "ru").strip(),
    LLM_MODELS=tuple(
        m.strip() for m in _env("LLM_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()
    ),
    BATCH_DELAY=_int("BATCH_DELAY", "180"),
    FORWARD_DELAY=_int("FORWARD_DELAY", "30"),
    TIMEZONE=_zone("TIMEZONE", "Europe/Moscow"),
    SEND_TRANSCRIPT=os.getenv("SEND_TRANSCRIPT", "1").strip().lower() not in ("0", "false", "no", "нет"),
    # STATE_DIRECTORY выставляет systemd (StateDirectory=), локально база ляжет рядом с ботом
    DB_PATH=os.getenv("DB_PATH") or os.path.join(os.getenv("STATE_DIRECTORY", "."), "tasks.db"),
    DIGEST_TIME=_clock("DIGEST_TIME", "09:00"),
)
