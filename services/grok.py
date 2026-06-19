import httpx
import json
from typing import List, Dict
from config import settings

GROK_MODEL = "grok-3-latest"  # или grok-3, grok-2 и т.д. Проверь актуальную модель

async def generate_response(
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    user_message: str,
    language: str = "ru"
) -> str:
    """
    Генерирует ответ через Grok API.
    chat_history — список [{"role": "user/assistant", "content": "..."}]
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Добавляем историю
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Текущее сообщение пользователя
    messages.append({"role": "user", "content": user_message})
    
    # Дополнительная инструкция по языку
    if language != "ru":
        lang_instruction = f"\n\nОтвечай на языке: {language}."
        messages[0]["content"] += lang_instruction

    payload = {
        "model": GROK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {settings.GROK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{settings.GROK_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[GROK ERROR] {e}")
            return "Извини, сейчас не могу ответить. Попробуй чуть позже."