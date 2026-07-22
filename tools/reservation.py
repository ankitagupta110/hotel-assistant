import uuid
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from database.models import Reservation, SessionLocal
from guardrails.pii import sanitize_reservation_for_response
from utils.logger import logger


class ReservationCreate(BaseModel):
    guest_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=32)
    check_in: date
    check_out: date
    room_type: Literal["standard", "deluxe", "suite"] = "standard"

    @field_validator("guest_name")
    @classmethod
    def normalize_guest_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Guest name is required.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must contain 7 to 15 digits.")
        return digits

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReservationCreate":
        if self.check_out <= self.check_in:
            raise ValueError("Check-out date must be after check-in date.")
        return self


class ReservationResponse(BaseModel):
    reservation_id: str
    guest_name: str
    email: str
    phone: str
    check_in: str
    check_out: str
    room_type: str
    status: str


def _to_response(reservation: Reservation) -> dict:
    return sanitize_reservation_for_response(
        {
            "reservation_id": reservation.reservation_id,
            "guest_name": reservation.guest_name,
            "email": reservation.email,
            "phone": reservation.phone,
            "check_in": reservation.check_in,
            "check_out": reservation.check_out,
            "room_type": reservation.room_type,
            "status": reservation.status,
        }
    )


def create_reservation(payload: ReservationCreate) -> dict:
    reservation_id = str(uuid.uuid4())
    with SessionLocal() as session:
        reservation = Reservation(
            reservation_id=reservation_id,
            guest_name=payload.guest_name,
            email=str(payload.email),
            phone=payload.phone,
            check_in=payload.check_in.isoformat(),
            check_out=payload.check_out.isoformat(),
            room_type=payload.room_type,
            status="confirmed",
        )
        session.add(reservation)
        session.commit()
        session.refresh(reservation)

    logger.info("Reservation created | reservation_id=%s", reservation_id)
    return _to_response(reservation)


def view_reservation(reservation_id: str) -> dict | None:
    with SessionLocal() as session:
        reservation = session.get(Reservation, reservation_id)
        if not reservation:
            return None
        return _to_response(reservation)


def list_reservations() -> list[dict]:
    with SessionLocal() as session:
        reservations = session.query(Reservation).order_by(Reservation.created_at.desc()).all()
        return [_to_response(reservation) for reservation in reservations]


def cancel_reservation(reservation_id: str) -> dict | None:
    with SessionLocal() as session:
        reservation = session.get(Reservation, reservation_id)
        if not reservation:
            return None
        if reservation.status == "cancelled":
            return _to_response(reservation)
        reservation.status = "cancelled"
        session.commit()
        session.refresh(reservation)

    logger.info("Reservation cancelled | reservation_id=%s", reservation_id)
    return _to_response(reservation)
