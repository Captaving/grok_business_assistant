from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, MessageOriginChannel, MessageOriginChat, MessageOriginHiddenUser, MessageOriginUser

from config import settings
from services.batcher import Batcher
from services.report import collect

router = Router()
# Всё, что пишут боту посторонние, молча игнорируется
router.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user.id == settings.OWNER_ID)

FORWARD_KEY = "forwarded"

HELP = f"""👋 Я делаю сводки по голосовым.

Как это работает:
1. Подключи меня: Настройки → Изменить профиль → Автоматизация чатов → выбери меня → «Только выбранные чаты» → чат с начальником.
2. Когда в этом чате придут голосовые, я подожду {settings.BATCH_DELAY // 60 or 1} мин тишины, расшифрую их и пришлю сюда сводку по задачам.
3. В чат с собеседником я ничего не пишу — только слушаю.

Ещё можно просто переслать мне голосовые — сделаю сводку через {settings.FORWARD_DELAY} с после последнего.

Команды:
/now — сделать сводку прямо сейчас, не дожидаясь паузы
/status — что сейчас в очереди"""


def _origin_name(message: Message) -> str:
    origin = message.forward_origin
    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.full_name
    if isinstance(origin, MessageOriginHiddenUser):
        return origin.sender_user_name
    if isinstance(origin, MessageOriginChat):
        return origin.sender_chat.full_name
    if isinstance(origin, MessageOriginChannel):
        return origin.chat.full_name
    return "Ты"


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message):
    await message.answer(HELP)


@router.message(Command("now"))
async def cmd_now(message: Message, batcher: Batcher):
    if batcher.flush_all():
        await message.answer("⏳ Делаю сводку…")
    else:
        await message.answer("Сводить пока нечего — новых голосовых нет.")


@router.message(Command("status"))
async def cmd_status(message: Message, batcher: Batcher):
    batches = batcher.pending()
    if not batches:
        await message.answer("Очередь пуста.")
        return
    lines = [f"• {b.title}: {len(b.entries)} сообщ." for b in batches]
    await message.answer("В очереди:\n" + "\n".join(lines) + "\n\n/now — свести сейчас")


@router.message(F.forward_origin | F.voice | F.audio | F.video_note)
async def on_forward(message: Message, bot: Bot, batcher: Batcher):
    is_new = collect(
        batcher, bot, message,
        key=FORWARD_KEY,
        title="Пересланные сообщения",
        sender=_origin_name(message),
        delay=settings.FORWARD_DELAY,
        require_media=False,
    )
    if is_new:
        await message.answer(f"📥 Принял. Сводка будет через {settings.FORWARD_DELAY} с после последнего сообщения (или /now).")


@router.message()
async def fallback(message: Message):
    await message.answer("Перешли мне голосовые или подключи меня к чату с начальником. Подробнее — /help")
