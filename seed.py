import asyncio
import logging

from sqlalchemy import select

from core.config import config
from db.session import AsyncSessionLocal
from db.models.setting import Setting
from services import settings as settings_svc


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed")


async def seed():
    async with AsyncSessionLocal() as session:
        for key, value in settings_svc.DEFAULTS.items():
            result = await session.execute(
                select(Setting).where(Setting.key == key)
            )
            if result.scalar_one_or_none() is None:
                session.add(Setting(key=key, value=str(value), type="string"))
                log.info(f"seed setting: {key} = {value}")
        await session.commit()

        await settings_svc.load_all(session)
        log.info(f"Super Admin ID: {config.SUPER_ADMIN_ID}")
        log.info("✅ Seed done")


if __name__ == "__main__":
    asyncio.run(seed())
