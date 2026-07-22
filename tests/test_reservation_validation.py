import unittest

from pydantic import ValidationError

from tools.reservation import ReservationCreate


class ReservationValidationTests(unittest.TestCase):
    def test_invalid_date_range_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ReservationCreate(
                guest_name="Ankit",
                email="ankit@example.com",
                phone="9876543210",
                check_in="2026-07-24",
                check_out="2026-07-23",
                room_type="suite",
            )

    def test_invalid_room_type_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ReservationCreate(
                guest_name="Ankit",
                email="ankit@example.com",
                phone="9876543210",
                check_in="2026-07-23",
                check_out="2026-07-24",
                room_type="penthouse",
            )

    def test_phone_is_normalized(self) -> None:
        reservation = ReservationCreate(
            guest_name="Ankit Sharma",
            email="ankit@example.com",
            phone="+91 98765-43210",
            check_in="2026-07-23",
            check_out="2026-07-24",
            room_type="standard",
        )

        self.assertEqual(reservation.phone, "919876543210")


if __name__ == "__main__":
    unittest.main()
