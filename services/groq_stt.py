import aiohttp

from config import settings
from services import groq


async def transcribe(audio: bytes, filename: str) -> str:
    """Распознаёт аудио через Groq Whisper. Формат Groq определяет по расширению filename."""

    def form() -> aiohttp.FormData:
        data = aiohttp.FormData()
        data.add_field("file", audio, filename=filename)
        data.add_field("model", settings.STT_MODEL)
        data.add_field("response_format", "json")
        data.add_field("temperature", "0")
        if settings.STT_LANGUAGE:
            data.add_field("language", settings.STT_LANGUAGE)
        return data

    result = await groq.request("/audio/transcriptions", form=form)
    return (result.get("text") or "").strip()
