from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from core.config import config
from db.models.user import User


class IsSuperAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id == config.SUPER_ADMIN_ID


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, user: User | None = None) -> bool:
        if event.from_user.id == config.SUPER_ADMIN_ID:
            return True
        if user is not None and user.role == "admin":
            return True
        return False


class IsUser(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, user: User | None = None) -> bool:
        if user is None:
            return False
        if event.from_user.id == config.SUPER_ADMIN_ID:
            return False
        return user.role in ("user", "reseller")


class IsReseller(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, user: User | None = None) -> bool:
        return user is not None and user.role == "reseller"
