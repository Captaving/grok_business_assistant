import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, BotCommandScopeChat, Message, MessageOriginChannel, MessageOriginChat, MessageOriginHiddenUser, MessageOriginUser

from config import settings
from services.batcher import Batcher
from services.report import collect, send_proposals
from services.task_views import MAIN_KB, draft_from_text
from services.tasks import TaskStore

log = logging.getLogger(__name__)
router = Router()
# Всё, что пишут боту посторонние, молча игнорируется
router.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user.id == settings.OWNER_ID)

FORWARD_KEY = "forwarded"

COMMANDS = [
    BotCommand(command="tasks", description="📋 Открытые задачи"),
    BotCommand(command="add", description="➕ Добавить задачу: /add текст"),
    BotCommand(command="today", description="📅 Что горит сегодня"),
    BotCommand(command="closed", description="✅ Закрытые задачи"),
    BotCommand(command="now", description="🎤 Свести голосовые сейчас"),
    BotCommand(command="status", description="⏳ Что в очереди"),
    BotCommand(command="help", description="❓ Как пользоваться"),
]

digest = f"в {settings.DIGEST_TIME[0]:02d}:{settings.DIGEST_TIME[1]:02d}" if settings.DIGEST_TIME else None
HELP = f"""👋 Я твой помощник по задачам от начальника.

🎤 Голосовые
Подключи меня: Настройки → Изменить профиль → Автоматизация чатов → выбери меня → «Только выбранные чаты» → чат с начальником. \
Когда придут голосовые, я подожду {max(settings.BATCH_DELAY // 60, 1)} мин тишины, расшифрую их и пришлю сюда сводку. \
По каждой найденной задаче спрошу, добавить ли её в список. В чат с собеседником я ничего не пишу.
Ещё голосовые можно просто переслать мне.

📋 Задачи
Кнопка «📋 Задачи» внизу — список открытых. В задаче: подробности, «✅ Закрыть» и «⏰ Напомнить».
Напиши мне любой текст — предложу сделать из него задачу.{f'''
Каждое утро {digest} пришлю, что горит.''' if digest else ''}

Команды:
/tasks — открытые задачи
/add текст — добавить задачу сразу
/today — что горит сегодня
/closed — закрытые (можно вернуть в работу)
/now — свести голосовые сейчас, не дожидаясь паузы
/status — что копится в очереди"""


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


async def set_commands(bot: Bot) -> None:
    """Меню команд видно только владельцу."""
    try:
        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(chat_id=settings.OWNER_ID))
    except TelegramAPIError as e:
        log.warning("Не удалось задать меню команд (напиши боту /start): %s", e)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await set_commands(bot)
    await message.answer(HELP, reply_markup=MAIN_KB)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP, reply_markup=MAIN_KB)


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


@router.message(F.text, ~F.text.startswith("/"))
async def text_to_task(message: Message, bot: Bot, store: TaskStore):
    await send_proposals(bot, store, [draft_from_text(message.text)], source="Ты")


@router.message()
async def fallback(message: Message):
    await message.answer("Не понял 🤔 Список команд — /help")
