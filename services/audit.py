from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.audit import AuditLog


async def log(
    session: AsyncSession,
    admin_id: int,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
):
    entry = AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        old_value=old_value,
        new_value=new_value,
    )
    session.add(entry)
    await session.commit()
    return entry


async def list_logs(session: AsyncSession, limit: int = 50, offset: int = 0):
    result = await session.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
