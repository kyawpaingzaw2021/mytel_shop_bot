from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from core.config import config
from db.models.user import User
from services import user as user_svc


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session is None:
            return await handler(event, data)

        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user is None:
            return await handler(event, data)

        if tg_user.id == config.SUPER_ADMIN_ID:
            data["user"] = None
            data["is_super_admin"] = True
            return await handler(event, data)

        user = await user_svc.get_or_create(
            session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

        if user.is_banned:
            if isinstance(event, Message):
                await event.answer("❌ သင်ဟာ ban ခံထားရပါတယ်")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Ban ခံထားရပါတယ်", show_alert=True)
            return

        data["user"] = user
        data["is_super_admin"] = False
        return await handler(event, data)
