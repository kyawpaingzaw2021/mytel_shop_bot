from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.audit import AuditLog


async def log(session, admin_id, action, target_type=None, target_id=None, old_value=None, new_value=None):
    entry = AuditLog(admin_id=admin_id, action=action, target_type=target_type,
        target_id=target_id, old_value=old_value, new_value=new_value)
    session.add(entry)
    await session.commit()
    return entry


async def list_logs(session: AsyncSession, limit=50, offset=0):
    result = await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all())
