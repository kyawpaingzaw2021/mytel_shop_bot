def mask_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = phone.strip()
    if len(phone) <= 8:
        return phone[:2] + "****"
    return phone[:5] + "****" + phone[-3:]


def mask_username(username: str | None, full_name: str | None = None) -> str:
    if username:
        u = username.lstrip("@")
        if len(u) <= 5:
            return "@" + u[:1] + "***"
        return "@" + u[:3] + "***" + u[-2:]
    if full_name:
        parts = full_name.split()
        first = parts[0]
        if len(first) <= 2:
            return first[:1] + "***"
        return first[:2] + "***"
    return "***"


def mask_phones(phones: list[str]) -> list[str]:
    return [mask_phone(p) for p in phones]
