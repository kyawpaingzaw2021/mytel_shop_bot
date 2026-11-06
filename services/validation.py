import re

PHONE_RE = re.compile(r"^09\d{7,9}$")


def validate_phone(phone: str) -> bool:
    if not phone: return False
    return bool(PHONE_RE.match(phone.strip()))


def validate_amount(amount: float, min_amount: float, max_amount: float) -> tuple[bool, str]:
    if amount <= 0: return False, "amount_positive"
    if amount < min_amount: return False, f"amount_min:{min_amount}"
    if amount > max_amount: return False, f"amount_max:{max_amount}"
    return True, ""
