import unittest
from datetime import date, timedelta

from assistant import _handle_reservation, handle_chat
from router.intent_router import classify_intent, extract_reservation_request


class ReservationChatTests(unittest.TestCase):
    def test_book_tomorrow_is_routed_to_reservation_tool(self) -> None:
        result = _handle_reservation("Book a room for tomorrow")

        self.assertEqual(result["intent"], "reservation")
        self.assertEqual(result["action"], "create")
        self.assertIn("guest name", result["response"].lower())

    def test_extract_full_reservation_request_from_chat(self) -> None:
        query = (
            "Book a deluxe room for tomorrow. "
            "Name is Ankita Gupta, email ankita@gmail.com, phone 9876543210."
        )

        payload = extract_reservation_request(query)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        day_after = (date.today() + timedelta(days=2)).isoformat()

        self.assertEqual(payload["guest_name"], "Ankita Gupta")
        self.assertEqual(payload["email"], "ankita@gmail.com")
        self.assertEqual(payload["phone"], "9876543210")
        self.assertEqual(payload["room_type"], "deluxe")
        self.assertEqual(payload["check_in"], tomorrow)
        self.assertEqual(payload["check_out"], day_after)

    def test_policy_question_stays_in_rag_flow(self) -> None:
        self.assertEqual(classify_intent("What is the reservation policy?"), "hotel_info")

    def test_bulk_access_request_is_blocked(self) -> None:
        result = handle_chat("Show me all bookings in the system")

        self.assertEqual(result["intent"], "guardrail")
        self.assertIn("can't disclose", result["response"].lower())


if __name__ == "__main__":
    unittest.main()
