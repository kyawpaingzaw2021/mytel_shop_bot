from aiogram import Router

from bot.handlers.admin import menu, items, orders, topups, users

router = Router(name="admin")
router.include_router(menu.router)
router.include_router(items.router)
router.include_router(orders.router)
router.include_router(topups.router)
router.include_router(users.router)

__all__ = ["router"]
