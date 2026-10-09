import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database.base import init_db, seed
from handlers import (admin, ai, announce, anon, assignments, fallback, library, manager, menu,
                      profile, rating, registration, schedule)
from middlewares.db import DbSessionMiddleware, ThrottleMiddleware
from services.scheduler import setup_scheduler


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN .env faylda ko'rsatilmagan!")
    await init_db()
    await seed()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())   # production: RedisStorage
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(ThrottleMiddleware())

    # Tartib muhim: ro'yxatdan o'tish -> menyu (FSM ni bekor qiladi) -> bo'limlar -> fallback
    dp.include_routers(
        registration.router, menu.router, profile.router, schedule.router, assignments.router,
        library.router, ai.router, rating.router, anon.router, announce.router,
        manager.router, admin.router, fallback.router,
    )

    scheduler = setup_scheduler(bot)
    scheduler.start()
    await bot.set_my_commands([BotCommand(command="start", description="Bosh menyu"),
                               BotCommand(command="cancel", description="Amalni bekor qilish"),
                               BotCommand(command="help", description="Yordam")])
    me = await bot.me()
    logging.info("Bot ishga tushdi: @%s", me.username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
