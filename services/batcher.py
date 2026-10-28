import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Entry:
    time: datetime
    sender: str
    text: str | None = None  # для текстовых сообщений
    task: asyncio.Task | None = None  # для голосовых: фоновая расшифровка

    @property
    def is_media(self) -> bool:
        return self.task is not None


@dataclass
class Batch:
    key: Any
    title: str
    delay: float
    require_media: bool  # пачку из одних текстов не сводим (иначе бот спамил бы на каждое «ок»)
    entries: list[Entry] = field(default_factory=list)
    timer: asyncio.Task | None = None


class Batcher:
    """Копит сообщения по чатам и отдаёт пачку на обработку после паузы."""

    def __init__(self, process: Callable[[Batch], Awaitable[None]], concurrency: int = 2):
        self._process = process
        self._batches: dict[Any, Batch] = {}
        # Groq на бесплатном тарифе пускает ~20 расшифровок в минуту — не шлём всё разом
        self._sem = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task] = set()  # держим ссылки, чтобы задачи не собрал GC

    def add_text(self, key, title, sender, time, text, *, delay, require_media=True) -> bool:
        return self._add(key, title, delay, require_media, Entry(time=time, sender=sender, text=text))

    def add_media(self, key, title, sender, time, transcribe: Coroutine, *, delay, require_media=True) -> bool:
        task = self._spawn(self._guarded(transcribe))
        return self._add(key, title, delay, require_media, Entry(time=time, sender=sender, task=task))

    def pending(self) -> list[Batch]:
        """Пачки, которые будут сведены, когда наступит пауза."""
        return [b for b in self._batches.values() if self._worth(b)]

    def flush_all(self) -> int:
        batches = self.pending()
        for batch in batches:
            if batch.timer:
                batch.timer.cancel()
            self._fire(batch.key)
        return len(batches)

    def _add(self, key, title, delay, require_media, entry: Entry) -> bool:
        """Возвращает True, если это первое сообщение новой пачки."""
        batch = self._batches.get(key)
        is_new = batch is None
        if is_new:
            batch = self._batches[key] = Batch(key=key, title=title, delay=delay, require_media=require_media)
        batch.entries.append(entry)
        if batch.timer:
            batch.timer.cancel()
        batch.timer = self._spawn(self._wait_and_fire(key, batch.delay))
        return is_new

    async def _wait_and_fire(self, key, delay: float) -> None:
        await asyncio.sleep(delay)
        self._fire(key)

    def _fire(self, key) -> None:
        # Без await: пачка снимается атомарно, новые сообщения пойдут уже в следующую
        batch = self._batches.pop(key, None)
        if batch is None:
            return
        if not self._worth(batch):
            log.info("Пачка %r без голосовых — пропускаю", batch.title)
            return
        self._spawn(self._run(batch))

    @staticmethod
    def _worth(batch: Batch) -> bool:
        return not batch.require_media or any(e.is_media for e in batch.entries)

    async def _run(self, batch: Batch) -> None:
        try:
            await self._process(batch)
        except Exception:
            log.exception("Не удалось обработать пачку %r", batch.title)

    async def _guarded(self, coro: Coroutine) -> str:
        async with self._sem:
            return await coro

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
