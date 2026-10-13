from aiogram import Router

from bot.handlers.user import start, order, wallet, history, support

router = Router(name="user")
router.include_router(start.router)
router.include_router(order.router)
router.include_router(wallet.router)
router.include_router(history.router)
router.include_router(support.router)

__all__ = ["router"]
