from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.item import Item, ItemTierPrice
from db.models.tier import Tier


async def create_item(
    session: AsyncSession,
    name: str,
    code: str,
    description: str | None,
    user_price: Decimal,
    tier_prices: dict[int, Decimal] | None = None,
) -> Item:
    item = Item(
        name=name,
        code=code.upper(),
        description=description,
        user_price=user_price,
        status="active",
    )
    session.add(item)
    await session.flush()

    if tier_prices:
        for tier_id, price in tier_prices.items():
            session.add(
                ItemTierPrice(item_id=item.id, tier_id=tier_id, price=price)
            )

    await session.commit()
    await session.refresh(item)
    return item


async def get_item(session: AsyncSession, item_id: int) -> Item | None:
    result = await session.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def get_by_code(session: AsyncSession, code: str) -> Item | None:
    result = await session.execute(
        select(Item).where(Item.code == code.upper())
    )
    return result.scalar_one_or_none()


async def list_active(session: AsyncSession):
    result = await session.execute(
        select(Item)
        .where(Item.status == "active")
        .order_by(Item.sort_order, Item.id)
    )
    return list(result.scalars().all())


async def list_all(session: AsyncSession):
    result = await session.execute(
        select(Item).order_by(Item.sort_order, Item.id)
    )
    return list(result.scalars().all())


async def update_item(session: AsyncSession, item: Item, **fields) -> Item:
    for key, value in fields.items():
        if hasattr(item, key):
            setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, item: Item) -> None:
    await session.delete(item)
    await session.commit()


async def toggle_status(session: AsyncSession, item: Item) -> Item:
    item.status = "inactive" if item.status == "active" else "active"
    await session.commit()
    await session.refresh(item)
    return item


async def get_price(
    session: AsyncSession, item_id: int, tier_id: int | None
) -> Decimal | None:
    if tier_id is None:
        result = await session.execute(
            select(Item.user_price).where(Item.id == item_id)
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(ItemTierPrice.price).where(
            ItemTierPrice.item_id == item_id,
            ItemTierPrice.tier_id == tier_id,
        )
    )
    return result.scalar_one_or_none()


async def set_tier_price(
    session: AsyncSession, item_id: int, tier_id: int, price: Decimal
) -> ItemTierPrice:
    result = await session.execute(
        select(ItemTierPrice).where(
            ItemTierPrice.item_id == item_id,
            ItemTierPrice.tier_id == tier_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ItemTierPrice(item_id=item_id, tier_id=tier_id, price=price)
        session.add(row)
    else:
        row.price = price
    await session.commit()
    await session.refresh(row)
    return row


async def get_tier_prices(session: AsyncSession, item_id: int) -> dict[int, Decimal]:
    result = await session.execute(
        select(ItemTierPrice).where(ItemTierPrice.item_id == item_id)
    )
    rows = result.scalars().all()
    return {row.tier_id: row.price for row in rows}
