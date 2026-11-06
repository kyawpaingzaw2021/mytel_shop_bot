from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from core.config import config
from db.models.user import User


class IsSuperAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id == config.SUPER_ADMIN_ID
