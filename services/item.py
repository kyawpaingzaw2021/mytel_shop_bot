from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.item import Item, ItemTierPrice


CATEGORIES = ["Mytel", "ATOM", "U9", "MPT", "Wifi", "Sim", "MLBB", "PUBG", "Other"]


def get_categories() -> list[str]:
    return list(CATEGORIES)


async def create_item(
    session: AsyncSession,
    name: str,
    code: str,
    description: str | None,
    user_price: Decimal,
    cost_price: Decimal | None = None,
    category: str = "Other",
    subcategory: str | None = None,
    tutorial_url: str | None = None,
    reseller_price: Decimal | None = None,
    form_type: str = 'phone',
    tier_prices: dict[int, Decimal] | None = None,
    note: str | None = None,
) -> Item:
    item = Item(
        category=category, subcategory=subcategory, name=name, code=code.upper(),
        description=description, tutorial_url=tutorial_url, user_price=user_price,
        cost_price=cost_price, reseller_price=reseller_price, form_type=form_type,
        note=note, status="active",
    )
    session.add(item)
    await session.flush()
    if tier_prices:
        for tier_id, price in tier_prices.items():
            session.add(ItemTierPrice(item_id=item.id, tier_id=tier_id, price=price))
    await session.commit()
    await session.refresh(item)
    return item


async def get_item(session, item_id: int) -> Item | None:
    result = await session.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def list_active(session):
    result = await session.execute(select(Item).where(Item.status == "active").order_by(Item.category, Item.sort_order, Item.id))
    return list(result.scalars().all())


async def list_all(session):
    result = await session.execute(select(Item).order_by(Item.category, Item.sort_order, Item.id))
    return list(result.scalars().all())


async def update_item(session, item: Item, **fields) -> Item:
    for key, value in fields.items():
        if hasattr(item, key):
            setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session, item: Item) -> None:
    await session.delete(item)
    await session.commit()


async def toggle_status(session, item: Item) -> Item:
    item.status = "inactive" if item.status == "active" else "active"
    await session.commit()
    await session.refresh(item)
    return item
