import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database as db
from handlers_user import router as user_router
from handlers_admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    await db.init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Передаём bot в хэндлеры через middleware
    from aiogram import BaseMiddleware
    from aiogram.types import TelegramObject
    from typing import Callable, Dict, Any, Awaitable

    class BotMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
        ) -> Any:
            data["bot"] = bot
            return await handler(event, data)

    dp.message.middleware(BotMiddleware())

    logger.info(f"Бот запущен. Admin ID: {config.ADMIN_ID}")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
