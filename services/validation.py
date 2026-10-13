import re
import unicodedata

PHONE_RE = re.compile(r"^09\d{7,9}$")
CODE_RE = re.compile(r"^[A-Z0-9_]{2,32}$")


def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.strip())


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    return bool(PHONE_RE.match(phone.strip()))


def validate_phones_list(phones: list[str], qty: int) -> tuple[bool, str]:
    cleaned = [p.strip() for p in phones if p.strip()]
    if len(cleaned) != qty:
        return False, f"phone_count_mismatch:{len(cleaned)}/{qty}"
    for p in cleaned:
        if not validate_phone(p):
            return False, f"phone_invalid:{p}"
    if len(set(cleaned)) != len(cleaned):
        return False, "phone_duplicate"
    return True, ""


def parse_phones(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def validate_amount(amount: float, min_amount: float, max_amount: float) -> tuple[bool, str]:
    if amount <= 0:
        return False, "amount_positive"
    if amount < min_amount:
        return False, f"amount_min:{min_amount}"
    if amount > max_amount:
        return False, f"amount_max:{max_amount}"
    return True, ""


def validate_item_name(name: str) -> bool:
    name = name.strip()
    return 2 <= len(name) <= 64


def validate_item_code(code: str) -> bool:
    return bool(CODE_RE.match(code.strip().upper()))


def validate_tier_name(name: str) -> bool:
    name = name.strip()
    return 2 <= len(name) <= 32


def validate_qty(qty: int) -> bool:
    return 1 <= qty <= 100
