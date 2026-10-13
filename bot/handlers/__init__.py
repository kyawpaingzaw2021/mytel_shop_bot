from aiogram import Router

from bot.handlers.user import router as user_router
from bot.handlers.admin import router as admin_router
from bot.handlers.superadmin import router as sa_router

router = Router(name="root")
router.include_router(user_router)
router.include_router(admin_router)
router.include_router(sa_router)

__all__ = ["router"]
