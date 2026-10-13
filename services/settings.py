from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings_cache import set_cache, get_cache, all_cache, clear_cache
from db.models.setting import Setting


DEFAULTS = {
    "payment_kpay": "",
    "payment_wave": "",
    "payment_name": "",
    "topup_min": "1000",
    "topup_max": "1000000",
    "reminder_interval": "30",
    "escalate_time": "120",
    "notic_channel_id": "0",
    "admin_group_id": "0",
    "daily_report_time": "00:00",
    "maintenance": "off",
    "maintenance_message": "ခေတ္တ ရပ်နားထားပါသည်",
    "welcome_message": "Mytel Data Shop မှ ကြိုဆိုပါတယ်",
    "support_contact": "",
}


async def load_all(session: AsyncSession) -> dict:
    clear_cache()
    result = await session.execute(select(Setting))
    rows = result.scalars().all()
    for row in rows:
        value = _cast(row.value, row.type)
        set_cache(row.key, value)
    for key, value in DEFAULTS.items():
        if key not in all_cache():
            set_cache(key, _cast(value, "string"))
    return all_cache()


async def get(session: AsyncSession, key: str, default=None):
    cached = get_cache(key)
    if cached is not None:
        return cached
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return DEFAULTS.get(key, default)
    value = _cast(row.value, row.type)
    set_cache(key, value)
    return value


async def update(session: AsyncSession, key: str, value, admin_id: int | None = None):
    str_value = str(value)
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = Setting(key=key, value=str_value, type="string", updated_by=admin_id)
        session.add(row)
    else:
        row.value = str_value
        row.updated_by = admin_id
    await session.commit()
    set_cache(key, value)


def _cast(value: str, type_: str):
    if type_ == "int":
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    if type_ == "bool":
        return value.lower() in ("true", "1", "yes", "on")
    return value
