from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.user import User
from db.models.wallet import WalletTransaction


async def get_balance(session: AsyncSession, user_id: int) -> Decimal:
    result = await session.execute(select(User.balance).where(User.id == user_id))
    return result.scalar_one() or Decimal("0")


async def _lock_user(session: AsyncSession, user_id: int) -> User:
    result = await session.execute(select(User).where(User.id == user_id).with_for_update())
    return result.scalar_one()


def _write_transaction(session, user_id, type_, amount, balance_after, ref_type, ref_id, note):
    tx = WalletTransaction(
        user_id=user_id, type=type_, amount=amount, balance_after=balance_after,
        ref_type=ref_type, ref_id=ref_id, note=note
    )
    session.add(tx)
    return tx


async def add_balance(session, user_id, amount, ref_type=None, ref_id=None, note=None, *, commit=True) -> Decimal:
    user = await _lock_user(session, user_id)
    user.balance = (user.balance or Decimal("0")) + amount
    _write_transaction(session, user_id, "topup", amount, user.balance, ref_type, ref_id, note)
    if commit:
        await session.commit()
    return user.balance


async def deduct_balance(session, user_id, amount, ref_type=None, ref_id=None, note=None, *, commit=True) -> Decimal:
    user = await _lock_user(session, user_id)
    current = user.balance or Decimal("0")
    if current < amount:
        raise ValueError("insufficient_balance")
    user.balance = current - amount
    _write_transaction(session, user_id, "deduct", -amount, user.balance, ref_type, ref_id, note)
    if commit:
        await session.commit()
    return user.balance


async def refund_balance(session, user_id, amount, ref_type=None, ref_id=None, note=None, *, commit=True) -> Decimal:
    user = await _lock_user(session, user_id)
    user.balance = (user.balance or Decimal("0")) + amount
    _write_transaction(session, user_id, "refund", amount, user.balance, ref_type, ref_id, note)
    if commit:
        await session.commit()
    return user.balance


async def list_transactions(session: AsyncSession, user_id: int, limit: int = 20, offset: int = 0):
    result = await session.execute(
        select(WalletTransaction).where(WalletTransaction.user_id == user_id)
        .order_by(WalletTransaction.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
