from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.topup import Topup
from services import wallet as wallet_svc


async def create_topup(session, user_id, amount, ss_file_id, sender_phone=None) -> Topup:
    topup = Topup(user_id=user_id, amount=amount, ss_file_id=ss_file_id, sender_phone=sender_phone, status="pending")
    session.add(topup)
    await session.commit()
    await session.refresh(topup)
    return topup


async def approve(session, topup_id, admin_id):
    result = await session.execute(select(Topup).where(Topup.id == topup_id).with_for_update())
    topup = result.scalar_one_or_none()
    if topup is None: return False, "not_found", None
    if topup.status != "pending": return False, "already_processed", topup
    await wallet_svc.add_balance(session, topup.user_id, topup.amount, ref_type="topup", ref_id=topup.id, note=f"Topup #{topup.id}")
    topup.status = "approved"
    topup.approved_by = admin_id
    await session.commit()
    await session.refresh(topup)
    return True, "ok", topup


async def reject(session, topup_id, admin_id):
    result = await session.execute(select(Topup).where(Topup.id == topup_id).with_for_update())
    topup = result.scalar_one_or_none()
    if topup is None: return False, "not_found", None
    if topup.status != "pending": return False, "already_processed", topup
    topup.status = "rejected"
    topup.approved_by = admin_id
    await session.commit()
    await session.refresh(topup)
    return True, "ok", topup
