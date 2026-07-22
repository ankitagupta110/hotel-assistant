import time
from datetime import date, timedelta

import httpx
import streamlit as st


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


st.set_page_config(page_title="Hotel Assistant", page_icon="🏨", layout="wide")


def _get_api_base_url() -> str:
    return st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")


def _request(method: str, path: str, **kwargs) -> tuple[dict | None, str | None, float]:
    started_at = time.perf_counter()
    url = f"{_get_api_base_url()}{path}"
    try:
        response = httpx.request(method, url, timeout=120.0, **kwargs)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        response.raise_for_status()
        return response.json(), None, elapsed_ms
    except httpx.HTTPStatusError as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        message = exc.response.text
        try:
            payload = exc.response.json()
            message = payload.get("detail") or payload.get("message") or message
        except ValueError:
            pass
        return None, f"Request failed: {message}", elapsed_ms
    except httpx.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return None, f"Connection failed: {exc}", elapsed_ms


def _render_chat_response(payload: dict) -> None:
    st.markdown(f"**Intent:** {payload.get('intent', 'unknown')}")
    st.write(payload.get("response", "No response returned."))
    if payload.get("action"):
        st.caption(f"Action: {payload['action']}")
    if payload.get("reservation"):
        st.json(payload["reservation"])


if "messages" not in st.session_state:
    st.session_state.messages = []


st.title("Hotel Reservation Assistant")
st.caption("Streamlit UI for your FastAPI hotel assistant")

with st.sidebar:
    st.header("Backend")
    st.text_input("API Base URL", key="api_base_url", value=DEFAULT_API_BASE_URL)

    if st.button("Check health"):
        data, error, elapsed_ms = _request("GET", "/health")
        if error:
            st.error(error)
        else:
            st.success(f"Backend is healthy in {elapsed_ms:.2f} ms")
            st.json(data)

st.subheader("Chat")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("payload"):
            payload = message["payload"]
            if payload.get("reservation"):
                st.json(payload["reservation"])
            if message.get("elapsed_ms") is not None:
                st.caption(f"API time: {message['elapsed_ms']:.2f} ms")

user_query = st.chat_input("Ask about the hotel or your reservation")
if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Getting answer from backend..."):
            payload, error, elapsed_ms = _request("POST", "/chat", json={"query": user_query})
        if error:
            st.error(error)
            assistant_message = {"role": "assistant", "content": error, "elapsed_ms": elapsed_ms}
        else:
            _render_chat_response(payload)
            st.caption(f"API time: {elapsed_ms:.2f} ms")
            assistant_message = {
                "role": "assistant",
                "content": payload.get("response", ""),
                "payload": payload,
                "elapsed_ms": elapsed_ms,
            }
        st.session_state.messages.append(assistant_message)

st.divider()
st.subheader("Reservation Actions")

chat_tab, create_tab, view_tab, view_all_tab, cancel_tab, dataset_tab = st.tabs(
    ["Guide", "Create", "View by ID", "View all", "Cancel", "Dataset"]
)

with chat_tab:
    st.write("Use chat for hotel questions, or use the tabs below for direct reservation APIs.")

with create_tab:
    with st.form("create_reservation_form"):
        guest_name = st.text_input("Guest Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        check_in = st.date_input("Check In", value=date.today() + timedelta(days=1))
        check_out = st.date_input("Check Out", value=date.today() + timedelta(days=2))
        room_type = st.selectbox("Room Type", options=["standard", "deluxe", "suite"])
        submitted = st.form_submit_button("Create reservation")

    if submitted:
        payload, error, elapsed_ms = _request(
            "POST",
            "/reservation/create",
            json={
                "guest_name": guest_name,
                "email": email,
                "phone": phone,
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "room_type": room_type,
            },
        )
        if error:
            st.error(error)
        else:
            st.success(f"Reservation created in {elapsed_ms:.2f} ms")
            st.write(payload.get("response", "Reservation created successfully."))
            if payload.get("reservation"):
                st.json(payload["reservation"])

with view_tab:
    reservation_id_to_view = st.text_input("Reservation ID", key="view_reservation_id")
    if st.button("View reservation", key="view_button"):
        if not reservation_id_to_view.strip():
            st.warning("Please enter a reservation ID.")
        else:
            payload, error, elapsed_ms = _request("GET", f"/reservation/{reservation_id_to_view.strip()}")
            if error:
                st.error(error)
            else:
                st.success(f"Reservation fetched in {elapsed_ms:.2f} ms")
                st.json(payload)

with view_all_tab:
    st.caption("Shows masked reservation data only for safe review.")
    if st.button("Load all reservations", key="view_all_button"):
        payload, error, elapsed_ms = _request("GET", "/reservations")
        if error:
            st.error(error)
        else:
            st.success(f"Loaded {payload.get('count', 0)} reservations in {elapsed_ms:.2f} ms")
            reservations = payload.get("reservations", [])
            if reservations:
                st.json(reservations)
            else:
                st.info("No reservations found.")

with cancel_tab:
    reservation_id_to_cancel = st.text_input("Reservation ID", key="cancel_reservation_id")
    if st.button("Cancel reservation", key="cancel_button"):
        if not reservation_id_to_cancel.strip():
            st.warning("Please enter a reservation ID.")
        else:
            payload, error, elapsed_ms = _request("DELETE", f"/reservation/{reservation_id_to_cancel.strip()}")
            if error:
                st.error(error)
            else:
                st.success(f"Reservation cancelled in {elapsed_ms:.2f} ms")
                st.write(payload.get("message", "Reservation cancelled successfully."))
                if payload.get("reservation"):
                    st.json(payload["reservation"])

with dataset_tab:
    st.write("Upload a new hotel document to replace the current knowledge base.")
    uploaded_file = st.file_uploader(
        "Upload a dataset file",
        type=["pdf", "txt", "md", "json"],
        key="dataset_upload",
    )
    if st.button("Re-upload dataset", key="upload_dataset_button"):
        if uploaded_file is None:
            st.warning("Please select a PDF, TXT, MD, or JSON file.")
        else:
            file_bytes = uploaded_file.getvalue()
            payload, error, elapsed_ms = _request(
                "POST",
                "/upload",
                files={"file": (uploaded_file.name, file_bytes, uploaded_file.type or "application/octet-stream")},
            )
            if error:
                st.error(error)
            else:
                st.success(f"Dataset uploaded in {elapsed_ms:.2f} ms")
                st.json(payload)
