from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.tier import Tier


async def list_all(session: AsyncSession):
    result = await session.execute(select(Tier).where(Tier.is_active == True).order_by(Tier.id))
    return list(result.scalars().all())
