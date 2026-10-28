import asyncio
import json
import logging
from typing import Any, Callable

import aiohttp

from config import settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
MAX_WAIT = 120  # если Groq просит ждать дольше — значит, кончился дневной лимит, ждать бессмысленно


class GroqError(Exception):
    pass


class ModelUnavailable(GroqError):
    """Модель выключили или переименовали — стоит попробовать запасную."""


async def request(
    path: str,
    *,
    payload: dict | None = None,
    form: Callable[[], aiohttp.FormData] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """POST в Groq API с повторами при 429/5xx и сетевых сбоях.

    form — фабрика FormData: aiohttp не умеет отправлять одну и ту же форму дважды.
    """
    url = f"{settings.GROQ_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait = min(2**attempt, 60)
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout), trust_env=True
            ) as session:
                async with session.post(
                    url, headers=headers, json=payload, data=form() if form else None
                ) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        return json.loads(body)

                    if resp.status == 429 or resp.status >= 500:
                        retry_after = resp.headers.get("retry-after")
                        if retry_after:
                            try:
                                wait = float(retry_after) + 1
                            except ValueError:
                                pass
                        if wait > MAX_WAIT:
                            raise GroqError(f"лимит Groq исчерпан, повтор возможен через {int(wait)} с")
                        log.warning("Groq %s, попытка %s/%s, жду %.0f с", resp.status, attempt, MAX_ATTEMPTS, wait)
                    elif resp.status == 404 or "model_not_found" in body or "decommissioned" in body:
                        raise ModelUnavailable(f"Groq {resp.status}: {body[:300]}")
                    else:
                        raise GroqError(f"Groq {resp.status}: {body[:300]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning("Сетевая ошибка Groq (%s), попытка %s/%s", e, attempt, MAX_ATTEMPTS)

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(wait)

    raise GroqError("Groq не ответил после нескольких попыток")
