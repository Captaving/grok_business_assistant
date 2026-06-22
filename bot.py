import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db

from handlers.start import router as start_router
from handlers.prompt import router as prompt_router
from handlers.settings import router as settings_router
from handlers.instructions import router as instructions_router
from handlers.test_mode import router as test_router
from handlers.business import router as business_router

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(prompt_router)
    dp.include_router(settings_router)
    dp.include_router(instructions_router)
    dp.include_router(test_router)
    dp.include_router(business_router)

    logging.info("Бот запущен...")

    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages"
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())