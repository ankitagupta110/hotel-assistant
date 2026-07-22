import re

OFF_TOPIC_PATTERNS = [
    r"\bgdp\b",
    r"\bstock\b",
    r"\bweather\b",
    r"\bpolitics\b",
    r"\belection\b",
    r"\bcrypto\b",
    r"\bbitcoin\b",
]

BULK_ACCESS_PATTERNS = [
    r"\ball\s+(reservations?|bookings?)\b",
    r"\bevery\s+(reservation|booking)\b",
    r"\blist\s+(all\s+)?(reservations?|bookings?|guests?)\b",
    r"\bshow\s+(me\s+)?all\s+(reservations?|bookings?)\b",
    r"\beveryone'?s?\s+(reservation|booking)\b",
]


def is_off_topic(query: str) -> bool:
    lowered = query.lower()
    return any(re.search(pattern, lowered) for pattern in OFF_TOPIC_PATTERNS)


def is_bulk_access_request(query: str) -> bool:
    lowered = query.lower()
    return any(re.search(pattern, lowered) for pattern in BULK_ACCESS_PATTERNS)


def off_topic_response() -> str:
    return (
        "I can only answer hotel-related questions or assist with reservations."
    )


def bulk_access_response() -> str:
    return (
        "Sorry, I can't disclose reservation information belonging to other guests."
    )
