import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from handlers.business import router as business_router
from handlers.owner import router as owner_router, set_commands
from handlers.tasks import router as tasks_router
from services import reminders
from services.batcher import Batcher
from services.report import make_processor, notify
from services.task_views import MAIN_KB
from services.tasks import TaskStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    store = TaskStore(settings.DB_PATH)
    dp = Dispatcher()
    dp["store"] = store
    dp["batcher"] = Batcher(process=make_processor(bot, store))
    # tasks раньше owner: у owner в конце «ловушка» для любого текста
    dp.include_routers(tasks_router, owner_router, business_router)

    me = await bot.get_me()
    log.info("Бот @%s запущен, владелец: %s, база: %s", me.username, settings.OWNER_ID, settings.DB_PATH)

    await set_commands(bot)
    await notify(bot, "🟢 Бот запущен. /help — как пользоваться", reply_markup=MAIN_KB)
    scheduler = asyncio.create_task(reminders.run(bot, store))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.cancel()


if __name__ == "__main__":
    asyncio.run(main())
