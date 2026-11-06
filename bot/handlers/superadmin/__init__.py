from aiogram import Router

from bot.handlers.superadmin import tiers, admins, settings, report

router = Router(name="superadmin")
router.include_router(tiers.router)
router.include_router(admins.router)
router.include_router(settings.router)
router.include_router(report.router)

__all__ = ["router"]
