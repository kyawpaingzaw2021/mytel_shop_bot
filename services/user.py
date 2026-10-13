from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        role="user",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_or_create(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> User:
    user = await get_by_telegram_id(session, telegram_id)
    if user is None:
        user = await register(session, telegram_id, username, full_name)
    return user


async def set_role(
    session: AsyncSession,
    user: User,
    role: str,
    tier_id: int | None = None,
) -> User:
    user.role = role
    user.tier_id = tier_id
    await session.commit()
    await session.refresh(user)
    return user


async def set_tier(session: AsyncSession, user: User, tier_id: int | None) -> User:
    user.tier_id = tier_id
    await session.commit()
    await session.refresh(user)
    return user


async def set_banned(session: AsyncSession, user: User, banned: bool) -> User:
    user.is_banned = banned
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(
    session: AsyncSession,
    role: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_users(session: AsyncSession, role: str | None = None) -> int:
    from sqlalchemy import func
    stmt = select(func.count()).select_from(User)
    if role:
        stmt = stmt.where(User.role == role)
    result = await session.execute(stmt)
    return result.scalar_one()
