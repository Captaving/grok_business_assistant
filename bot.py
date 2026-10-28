import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat

from config import settings
from handlers.business import router as business_router
from handlers.owner import router as owner_router
from services.batcher import Batcher
from services.report import make_processor, notify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")


async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    dp["batcher"] = Batcher(process=make_processor(bot))
    dp.include_routers(owner_router, business_router)

    me = await bot.get_me()
    log.info("Бот @%s запущен, владелец: %s", me.username, settings.OWNER_ID)

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="now", description="Сводка прямо сейчас"),
                BotCommand(command="status", description="Что в очереди"),
                BotCommand(command="help", description="Как пользоваться"),
            ],
            scope=BotCommandScopeChat(chat_id=settings.OWNER_ID),
        )
    except TelegramAPIError as e:
        log.warning("Не удалось задать меню команд (напиши боту /start): %s", e)

    await notify(bot, "🟢 Бот запущен. /help — как пользоваться")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
