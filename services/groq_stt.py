import httpx
import os
from config import settings

async def transcribe_audio(file_path: str) -> str:
    """
    Распознаёт голосовое сообщение через Groq Whisper.
    """
    url = f"{settings.GROQ_BASE_URL}/audio/transcriptions"
    
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}"
    }
    
    data = {
        "model": "whisper-large-v3",
        "response_format": "json",
        "language": "ru"  # можно сделать динамическим
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(file_path, "rb") as audio_file:
            files = {"file": (os.path.basename(file_path), audio_file, "audio/ogg")}
            try:
                response = await client.post(url, headers=headers, data=data, files=files)
                response.raise_for_status()
                result = response.json()
                return result.get("text", "").strip()
            except Exception as e:
                print(f"[GROQ STT ERROR] {e}")
                return ""