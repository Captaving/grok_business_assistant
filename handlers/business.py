import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BusinessConnection, Message

from config import settings
from services.batcher import Batcher
from services.report import collect, notify

log = logging.getLogger(__name__)
router = Router()

# business_connection_id -> id того, кто подключил бота
_connection_owner: dict[str, int] = {}


@router.business_connection()
async def on_connection(connection: BusinessConnection, bot: Bot):
    _connection_owner[connection.id] = connection.user.id
    if connection.user.id != settings.OWNER_ID:
        log.warning("Бота подключил посторонний: %s (%s) — игнорирую", connection.user.full_name, connection.user.id)
        return

    if not connection.is_enabled:
        await notify(bot, "⛔ Меня отключили от твоих чатов. Сводок больше не будет.")
        return

    text = "✅ Подключено! Жду голосовые в выбранных чатах — сводка придёт сюда."
    if connection.rights and connection.rights.can_reply:
        text += (
            "\n\nℹ️ Право отвечать на сообщения мне не нужно — я ничего не пишу в твои чаты. "
            "Можно выключить в «Автоматизации чатов»."
        )
    await notify(bot, text)


async def _owner_of(bot: Bot, connection_id: str) -> int | None:
    if connection_id not in _connection_owner:
        try:
            connection = await bot.get_business_connection(connection_id)
        except TelegramAPIError as e:
            log.warning("Не удалось получить подключение %s: %s", connection_id, e)
            return None
        _connection_owner[connection_id] = connection.user.id
    return _connection_owner[connection_id]


@router.business_message()
async def on_business_message(message: Message, bot: Bot, batcher: Batcher):
    if not message.business_connection_id:
        return
    if await _owner_of(bot, message.business_connection_id) != settings.OWNER_ID:
        return
    # Свои исходящие (и отправленные ботами от твоего имени) не сводим
    if message.sender_business_bot or (message.from_user and message.from_user.id == settings.OWNER_ID):
        return

    # Сюда ничего не отправляем: бот в чате с собеседником только слушает
    collect(
        batcher, bot, message,
        key=message.chat.id,
        title=message.chat.full_name,
        sender=message.from_user.full_name if message.from_user else message.chat.full_name,
        delay=settings.BATCH_DELAY,
        require_media=True,
    )
