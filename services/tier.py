from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.tier import Tier
from db.models.item import ItemTierPrice


async def create_tier(session: AsyncSession, name: str) -> Tier:
    tier = Tier(name=name, is_active=True)
    session.add(tier)
    await session.commit()
    await session.refresh(tier)
    return tier


async def get_tier(session: AsyncSession, tier_id: int) -> Tier | None:
    result = await session.execute(select(Tier).where(Tier.id == tier_id))
    return result.scalar_one_or_none()


async def get_by_name(session: AsyncSession, name: str) -> Tier | None:
    result = await session.execute(select(Tier).where(Tier.name == name))
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession):
    result = await session.execute(
        select(Tier).where(Tier.is_active == True).order_by(Tier.id)  # noqa
    )
    return list(result.scalars().all())


async def update_tier(session: AsyncSession, tier: Tier, name: str) -> Tier:
    tier.name = name
    await session.commit()
    await session.refresh(tier)
    return tier


async def delete_tier(session: AsyncSession, tier: Tier) -> None:
    await session.delete(tier)
    await session.commit()


async def copy_prices(
    session: AsyncSession, source_tier_id: int, new_tier_id: int
) -> int:
    result = await session.execute(
        select(ItemTierPrice).where(ItemTierPrice.tier_id == source_tier_id)
    )
    rows = result.scalars().all()
    count = 0
    for row in rows:
        session.add(
            ItemTierPrice(
                item_id=row.item_id,
                tier_id=new_tier_id,
                price=row.price,
            )
        )
        count += 1
    await session.commit()
    return count


async def count_items(session: AsyncSession, tier_id: int) -> int:
    from sqlalchemy import func
    result = await session.execute(
        select(func.count())
        .select_from(ItemTierPrice)
        .where(ItemTierPrice.tier_id == tier_id)
    )
    return result.scalar_one()
