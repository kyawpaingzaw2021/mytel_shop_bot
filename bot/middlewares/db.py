from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from db.session import AsyncSessionLocal


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)
