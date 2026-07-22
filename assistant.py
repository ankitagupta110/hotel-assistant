from time import perf_counter

from pydantic import ValidationError

from guardrails.security import (
    bulk_access_response,
    is_bulk_access_request,
    is_off_topic,
    off_topic_response,
)
from rag.prompt import NOT_FOUND_MESSAGE
from rag.retriever import retrieve_context
from router.intent_router import (
    classify_intent,
    extract_reservation_id,
    extract_reservation_request,
    missing_reservation_fields,
    reservation_action,
)
from tools.reservation import cancel_reservation, create_reservation, view_reservation
from tools.reservation import ReservationCreate
from utils.llm import get_llm_client
from utils.logger import logger


def handle_chat(query: str) -> dict:
    request_started_at = perf_counter()

    if is_bulk_access_request(query):
        result = {"intent": "guardrail", "response": bulk_access_response()}
        logger.info(
            "Chat timing | intent=%s | total=%.2f ms",
            result["intent"],
            (perf_counter() - request_started_at) * 1000,
        )
        return result

    if is_off_topic(query):
        result = {"intent": "guardrail", "response": off_topic_response()}
        logger.info(
            "Chat timing | intent=%s | total=%.2f ms",
            result["intent"],
            (perf_counter() - request_started_at) * 1000,
        )
        return result

    intent = classify_intent(query)

    if intent == "reservation":
        result = _handle_reservation(query)
        logger.info(
            "Chat timing | intent=%s | total=%.2f ms",
            result["intent"],
            (perf_counter() - request_started_at) * 1000,
        )
        return result

    retrieval_started_at = perf_counter()
    context = retrieve_context(query)
    retrieval_ms = (perf_counter() - retrieval_started_at) * 1000
    if not context.strip():
        result = {"intent": "hotel_info", "response": NOT_FOUND_MESSAGE}
        logger.info(
            "Chat timing | intent=%s | retrieve=%.2f ms | llm=%.2f ms | total=%.2f ms",
            result["intent"],
            retrieval_ms,
            0.0,
            (perf_counter() - request_started_at) * 1000,
        )
        return result

    llm_started_at = perf_counter()
    llm_source = "provider"
    try:
        answer = get_llm_client().generate_rag_answer(query, context)
    except Exception:
        llm_source = "fallback_exception"
        answer = _build_fallback_answer(query, context)
    llm_ms = (perf_counter() - llm_started_at) * 1000

    if not answer or answer == "":
        fallback_started_at = perf_counter()
        answer = _build_fallback_answer(query, context)
        llm_ms += (perf_counter() - fallback_started_at) * 1000
        llm_source = "fallback_empty"

    result = {"intent": "hotel_info", "response": answer}
    logger.info(
        "Chat timing | intent=%s | retrieve=%.2f ms | llm=%.2f ms | total=%.2f ms | source=%s",
        result["intent"],
        retrieval_ms,
        llm_ms,
        (perf_counter() - request_started_at) * 1000,
        llm_source,
    )
    return result


def _handle_reservation(query: str) -> dict:
    action = reservation_action(query)

    if action == "create":
        payload = extract_reservation_request(query)
        missing_fields = missing_reservation_fields(payload)
        if missing_fields:
            friendly_names = {
                "guest_name": "guest name",
                "email": "email",
                "phone": "phone number",
                "check_in": "check-in date",
                "check_out": "check-out date",
                "room_type": "room type",
            }
            missing_text = ", ".join(friendly_names[field] for field in missing_fields)
            return {
                "intent": "reservation",
                "action": "create",
                "response": (
                    "I can create your reservation, but I still need your "
                    f"{missing_text}. Please include them in one message, for example: "
                    "'Book a deluxe room for tomorrow, name is Ankit Sharma, "
                    "email ankit@example.com, phone 9876543210.'"
                ),
            }

        try:
            reservation_payload = ReservationCreate(**payload)
        except ValidationError as exc:
            return {
                "intent": "reservation",
                "action": "create",
                "response": f"I couldn't create the reservation because some details are invalid: {exc.errors()[0]['msg']}",
            }

        reservation = create_reservation(reservation_payload)
        return {
            "intent": "reservation",
            "action": "create",
            "response": (
                "Reservation created successfully. "
                f"Your reservation ID is {reservation['reservation_id']}."
            ),
            "reservation": reservation,
        }

    reservation_id = extract_reservation_id(query)
    if not reservation_id:
        return {
            "intent": "reservation",
            "response": (
                "Please provide your reservation ID so I can view or cancel your booking."
            ),
        }

    if action == "cancel":
        result = cancel_reservation(reservation_id)
        if not result:
            return {
                "intent": "reservation",
                "action": "cancel",
                "response": "Reservation not found.",
            }
        return {
            "intent": "reservation",
            "action": "cancel",
            "response": f"Reservation {reservation_id} has been cancelled.",
            "reservation": result,
        }

    result = view_reservation(reservation_id)
    if not result:
        return {
            "intent": "reservation",
            "action": "view",
            "response": "Reservation not found.",
        }
    return {
        "intent": "reservation",
        "action": "view",
        "response": f"Here are the details for reservation {reservation_id}.",
        "reservation": result,
    }


def _build_fallback_answer(question: str, context: str) -> str:
    cleaned_context = " ".join(context.split())
    if not cleaned_context:
        return NOT_FOUND_MESSAGE

    lower_question = question.lower().strip()
    if not lower_question:
        return f"According to the hotel guide, {cleaned_context[:400]}"

    sentences = [segment.strip() for segment in cleaned_context.split(".") if segment.strip()]
    if not sentences:
        return f"According to the hotel guide, {cleaned_context[:400]}"

    question_keywords = [word for word in lower_question.replace("?", "").split() if len(word) > 2]
    scored_sentences = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        score = sum(1 for keyword in question_keywords if keyword in sentence_lower)
        scored_sentences.append((score, sentence))

    scored_sentences.sort(key=lambda item: item[0], reverse=True)
    best_sentence = scored_sentences[0][1] if scored_sentences and scored_sentences[0][0] > 0 else sentences[0]

    if any(keyword in lower_question for keyword in ("dish", "food", "restaurant", "breakfast", "dining", "meal", "hygiene", "clean", "sanit", "health", "safety", "covid")):
        return f"Based on the hotel guide, {best_sentence.lower()}"

    if len(best_sentence) > 220:
        return f"Based on the hotel guide, {best_sentence[:220].rstrip()}..."

    return f"Based on the hotel guide, {best_sentence.lower()}"


def create_reservation_from_api(payload: ReservationCreate) -> dict:
    reservation = create_reservation(payload)
    return {
        "intent": "reservation",
        "action": "create",
        "response": f"Reservation created successfully. Your reservation ID is {reservation['reservation_id']}.",
        "reservation": reservation,
    }
