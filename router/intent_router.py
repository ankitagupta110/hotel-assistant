import re
from datetime import date, timedelta

CREATE_KEYWORDS = [
    "book",
    "reserve",
    "make a reservation",
    "create reservation",
    "create booking",
    "new booking",
]

RESERVATION_KEYWORDS = [
    "cancel reservation",
    "cancel booking",
    "view reservation",
    "view booking",
    "check reservation",
    "check booking",
    "my reservation",
    "my booking",
    "reservation id",
]

VIEW_KEYWORDS = [
    "view reservation",
    "view booking",
    "check reservation",
    "check booking",
    "show my booking",
    "show my reservation",
    "my reservation",
    "my booking",
]

CANCEL_KEYWORDS = [
    "cancel reservation",
    "cancel booking",
    "cancel my reservation",
    "cancel my booking",
]

ROOM_TYPES = ("standard", "deluxe", "suite")


def classify_intent(query: str) -> str:
    lowered = query.lower().strip()
    if extract_reservation_id(query):
        return "reservation"
    if any(keyword in lowered for keyword in RESERVATION_KEYWORDS):
        return "reservation"
    if any(keyword in lowered for keyword in CREATE_KEYWORDS):
        return "reservation"
    return "hotel_info"


def reservation_action(query: str) -> str:
    lowered = query.lower()
    if any(keyword in lowered for keyword in CANCEL_KEYWORDS) or "cancel" in lowered:
        return "cancel"
    if extract_reservation_id(query) and any(word in lowered for word in ("view", "check", "show", "my booking", "my reservation", "status")):
        return "view"
    if any(keyword in lowered for keyword in VIEW_KEYWORDS):
        return "view"
    if any(keyword in lowered for keyword in CREATE_KEYWORDS):
        return "create"
    return "unknown"


def extract_reservation_id(query: str) -> str | None:
    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        query,
        re.IGNORECASE,
    )
    return match.group(0) if match else None


def extract_reservation_request(query: str) -> dict[str, str]:
    lowered = query.lower()
    payload: dict[str, str] = {}

    name_match = re.search(
        r"(?:name\s*(?:is|:)|guest\s+name\s*(?:is|:))\s*([a-z][a-z .'-]{1,118})",
        query,
        re.IGNORECASE,
    )
    if name_match:
        payload["guest_name"] = " ".join(name_match.group(1).strip().split())

    email_match = re.search(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", query, re.IGNORECASE)
    if email_match:
        payload["email"] = email_match.group(0)

    phone_match = re.search(r"(?:phone|mobile|contact)\s*(?:is|:)?\s*([\d\s()+\-]{7,20})", query, re.IGNORECASE)
    if not phone_match:
        phone_match = re.search(r"\b(?:\+?\d[\d\s()-]{6,}\d)\b", query)
    if phone_match:
        payload["phone"] = re.sub(r"\D", "", phone_match.group(1) if phone_match.lastindex else phone_match.group(0))

    for room_type in ROOM_TYPES:
        if room_type in lowered:
            payload["room_type"] = room_type
            break

    payload.update(_extract_stay_dates(query))
    return payload


def missing_reservation_fields(payload: dict[str, str]) -> list[str]:
    required_fields = ["guest_name", "email", "phone", "check_in", "check_out", "room_type"]
    return [field for field in required_fields if not payload.get(field)]


def _extract_stay_dates(query: str) -> dict[str, str]:
    lowered = query.lower()
    stay: dict[str, str] = {}

    check_in_match = re.search(r"check[\s-]?in\s*(?:is|:)?\s*(\d{4}-\d{2}-\d{2})", lowered)
    check_out_match = re.search(r"check[\s-]?out\s*(?:is|:)?\s*(\d{4}-\d{2}-\d{2})", lowered)
    if check_in_match:
        stay["check_in"] = check_in_match.group(1)
    if check_out_match:
        stay["check_out"] = check_out_match.group(1)
    if stay.get("check_in") and stay.get("check_out"):
        return stay

    range_match = re.search(r"\bfrom\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})\b", lowered)
    if range_match:
        return {"check_in": range_match.group(1), "check_out": range_match.group(2)}

    explicit_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", lowered)
    if len(explicit_dates) >= 2:
        return {"check_in": explicit_dates[0], "check_out": explicit_dates[1]}
    if len(explicit_dates) == 1:
        check_in = date.fromisoformat(explicit_dates[0])
        return {
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
        }

    base_date: date | None = None
    if "day after tomorrow" in lowered:
        base_date = date.today() + timedelta(days=2)
    elif "tomorrow" in lowered:
        base_date = date.today() + timedelta(days=1)
    elif "today" in lowered or "tonight" in lowered:
        base_date = date.today()

    if base_date is None:
        return {}

    return {
        "check_in": base_date.isoformat(),
        "check_out": (base_date + timedelta(days=1)).isoformat(),
    }
