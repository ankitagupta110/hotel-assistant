import re


def mask_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return "*"
    return cleaned[0] + "*" * (len(cleaned) - 1)


def mask_email(email: str) -> str:
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "****"
    else:
        masked_local = local[:2] + "****"
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "*" * len(digits)
    return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]


def sanitize_reservation_for_response(data: dict) -> dict:
    sanitized = dict(data)
    if sanitized.get("guest_name"):
        sanitized["guest_name"] = mask_name(sanitized["guest_name"])
    if sanitized.get("email"):
        sanitized["email"] = mask_email(sanitized["email"])
    if sanitized.get("phone"):
        sanitized["phone"] = mask_phone(sanitized["phone"])
    return sanitized
