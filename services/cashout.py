from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.cashout import Cashout
from services import wallet as wallet_svc


async def create_cashout(session, user_id, amount, account_name, phone) -> Cashout:
    await wallet_svc.deduct_balance(session, user_id, amount, ref_type="cashout", note="Cash Out Request")
    cashout = Cashout(user_id=user_id, amount=amount, account_name=account_name, phone=phone, status="pending")
    session.add(cashout)
    await session.commit()
    await session.refresh(cashout)
    return cashout


async def approve(session, cashout_id, admin_id):
    result = await session.execute(select(Cashout).where(Cashout.id == cashout_id).with_for_update())
    cashout = result.scalar_one_or_none()
    if cashout is None: return False, "not_found", None
    if cashout.status != "pending": return False, "already_processed", cashout
    cashout.status = "approved"
    cashout.approved_by = admin_id
    await session.commit()
    await session.refresh(cashout)
    return True, "ok", cashout


async def reject(session, cashout_id, admin_id):
    result = await session.execute(select(Cashout).where(Cashout.id == cashout_id).with_for_update())
    cashout = result.scalar_one_or_none()
    if cashout is None: return False, "not_found", None
    if cashout.status != "pending": return False, "already_processed", cashout
    await wallet_svc.refund_balance(session, cashout.user_id, cashout.amount, ref_type="cashout", note="Cash Out Rejected")
    cashout.status = "rejected"
    cashout.approved_by = admin_id
    await session.commit()
    await session.refresh(cashout)
    return True, "ok", cashout
