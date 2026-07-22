# Hotel Reservation Assistant

AI-powered hotel assistant with document-grounded hotel Q&A, reservation tools, basic guardrails, and PII-safe responses.

## Features

- **RAG Q&A** — Answers hotel questions from the provided PDF only
- **Reservations** — Create, view, and cancel bookings via API, plus chat-triggered reservation tool calls
- **Dataset refresh** — Upload a new PDF, TXT, MD, or JSON file and re-ingest it
- **Intent routing** — Routes between RAG answers and reservation tools
- **Guardrails** — Blocks off-topic queries and bulk reservation access in chat
- **PII protection** — Masks guest name, email, and phone in responses; avoids logging raw PII

## Supported models

The app supports these answer-generation providers:

- `ollama` for local LLM inference
- `huggingface` for hosted inference
- `openai` for hosted inference
- `auto` to try configured providers in fallback order

Recommended local setup for this task:

- `LLM_PROVIDER=ollama`
- `OLLAMA_MODEL=llama3.2`
- `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`

## Setup

1. **Create virtual environment and install dependencies**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**

```bash
copy .env.example .env
```

Edit `.env` and choose one provider:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

Or:

```env
LLM_PROVIDER=huggingface
HF_API_KEY=hf_xxxxxxxx
HF_MODEL=microsoft/Phi-3.5-mini-instruct
```

Or:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4o-mini
```

3. **Place the hotel PDF**

The PDF should be available at `data/hotel.pdf`.

4. **Run the backend**

```bash
py main.py --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API.

The reservation database is stored in the project as `hotel_reservations.db`.

5. **Run the Streamlit UI**

```bash
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501) for the UI.

## Architecture overview

- `app.py` exposes FastAPI endpoints and startup ingestion.
- `assistant.py` applies guardrails and routes requests to RAG or reservation tools.
- `rag/` ingests the hotel guide, chunks it, and retrieves matching context.
- `tools/reservation.py` validates reservation input and handles create, view, cancel, and masked listing.
- `database/models.py` stores reservations in SQLite through SQLAlchemy.
- `router/intent_router.py` classifies chat intents and extracts reservation details from natural language.
- `guardrails/` blocks off-topic or bulk-data requests and masks PII.
- `streamlit_app.py` provides a basic UI over the backend APIs.

## Key design decisions

- Keep the backend simple with FastAPI, SQLite, and small service modules.
- Use retrieval over the uploaded hotel guide so answers stay grounded in the document.
- Separate hotel-information answers from transactional reservation tool calls.
- Allow chat to trigger reservation tools only when enough details are present; otherwise ask for the missing fields.
- Sanitize reservation responses before returning them so UI and API consumers do not see raw PII.
- Keep bulk reservation access blocked in chat, while a separate direct API view returns masked records for controlled review in the UI.

## Assumptions

- The hotel guide is the only trusted source for hotel-information answers.
- A simple SQLite database is enough for this task and single-user local testing.
- The Streamlit UI is meant for local demo/testing, not a production-grade frontend.
- The masked `view all reservations` screen is for safe inspection and debugging, not for unrestricted guest-data export.
- Chat-based reservation creation expects all required fields in one message: guest name, email, phone, stay dates, and room type.

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Main assistant — routes to RAG or reservation logic |
| POST | `/reservation/create` | Create a reservation |
| GET | `/reservation/{id}` | View a reservation with masked PII |
| GET | `/reservations` | View all reservations with masked PII |
| DELETE | `/reservation/{id}` | Cancel a reservation |
| POST | `/upload` | Replace and re-ingest the hotel knowledge document |
| GET | `/health` | Health check |

## Example requests

**Hotel question (RAG):**

```json
POST /chat
{ "query": "What is the cancellation policy?" }
```

**Create reservation via API:**

```json
POST /reservation/create
{
  "guest_name": "Ankita",
  "email": "ankita@gmail.com",
  "phone": "9876543210",
  "check_in": "2026-07-20",
  "check_out": "2026-07-22",
  "room_type": "deluxe"
}
```

**Create reservation via chat:**

```json
POST /chat
{
  "query": "Book a deluxe room for tomorrow. Name is Ankita Gupta, email ankita@gmail.com, phone 9876543210."
}
```

**View via chat:**

```json
POST /chat
{ "query": "Show my booking <reservation-id>" }
```

## Sample queries used for testing

- `What is the cancellation policy?`
- `Is vegetarian food available?`
- `How does the hotel ensure hygiene?`
- `Book a room for tomorrow`
- `Book a deluxe room for tomorrow. Name is Ankita Gupta, email ankita@gmail.com, phone 9876543210.`
- `Show my booking <reservation-id>`
- `Cancel reservation <reservation-id>`

## Tests

Run the focused unit tests with:

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
hotel-assistant/
├── .env.example
├── app.py
├── main.py
├── assistant.py
├── config.py
├── requirements.txt
├── streamlit_app.py
├── hotel_reservations.db
├── data/hotel.pdf
├── database/
│   ├── database.py
│   └── models.py
├── guardrails/
│   ├── pii.py
│   └── security.py
├── rag/
│   ├── ingest.py
│   ├── prompt.py
│   └── retriever.py
├── router/
│   └── intent_router.py
├── tests/
├── tools/
│   └── reservation.py
└── utils/
    ├── llm.py
    └── logger.py
```
