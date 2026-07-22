# Hotel Assistant Code Wiki

## Overview

`hotel-assistant` is a FastAPI service that combines two capabilities:

1. Hotel information Q&A using retrieval-augmented generation (RAG) over a local hotel guide PDF.
2. Reservation management using a SQLite database and simple CRUD-style service functions.

The system is intentionally lightweight. It does not use an agent framework or external workflow engine. Instead, it relies on small, focused Python modules connected through a straightforward request flow.

## High-Level Architecture

```text
Client
  |
  v
FastAPI app (`app.py`)
  |
  +--> Startup lifecycle
  |      +--> Initialize SQLite tables
  |      +--> Ingest hotel PDF into retrieval index
  |
  +--> `/chat`
  |      +--> `assistant.handle_chat()`
  |             +--> Guardrails
  |             +--> Intent router
  |             +--> Reservation service
  |             \--> RAG retriever + LLM provider
  |
  +--> `/reservation/*`
  |      \--> Reservation service
  |
  \--> `/upload`
         \--> RAG ingestion pipeline
```

## Request Flows

### Hotel Q&A Flow

1. The client sends a question to `POST /chat`.
2. `app.py` forwards the text to `assistant.handle_chat()`.
3. `assistant.py` runs safety checks from `guardrails/security.py`.
4. `router/intent_router.py` classifies the query as `hotel_info`.
5. `rag/retriever.py` fetches the most relevant chunks from the in-memory retrieval collection.
6. `utils/llm.py` formats the prompt and asks the configured LLM provider to answer using the retrieved context only.
7. If the LLM provider fails, the assistant falls back to a local extractive answer built from the retrieved text.

### Reservation Flow

1. The client either calls reservation APIs directly or submits a reservation-related message to `POST /chat`.
2. `assistant.py` routes the request to the reservation tool functions.
3. `tools/reservation.py` uses SQLAlchemy sessions from `database/models.py`.
4. Reservation responses are sanitized through `guardrails/pii.py` before being returned.

### Dataset Upload Flow

1. The client uploads a PDF, text, markdown, or JSON file to `POST /upload`.
2. `app.py` stores the uploaded data or decodes text.
3. `rag/ingest.py` normalizes and chunks the content.
4. The chunks are loaded into an in-memory retrieval structure used by the chat flow.

## Repository Structure

```text
hotel-assistant/
├── app.py
├── assistant.py
├── config.py
├── requirements.txt
├── .env
├── data/
│   ├── hotel.pdf
│   └── hotel_rag_document_v2.pdf
├── database/
│   ├── database.py
│   └── models.py
├── docs/
│   └── CODE_WIKI.md
├── guardrails/
│   ├── pii.py
│   └── security.py
├── rag/
│   ├── ingest.py
│   ├── prompt.py
│   └── retriever.py
├── router/
│   └── intent_router.py
├── tools/
│   └── reservation.py
└── utils/
    ├── llm.py
    └── logger.py
```

## Module Responsibilities

### `app.py`

Primary web entry point.

Responsibilities:

- Creates the FastAPI application.
- Defines request and response models for chat.
- Initializes the database and RAG index during startup.
- Exposes the main HTTP endpoints:
  - `GET /health`
  - `POST /chat`
  - `POST /reservation/create`
  - `GET /reservation/{reservation_id}`
  - `DELETE /reservation/{reservation_id}`
  - `POST /upload`

Key symbols:

- `lifespan()` initializes the database and performs PDF ingestion on startup.
- `ChatRequest` validates chat input.
- `ChatResponse` shapes chat output.
- `chat()` delegates to `assistant.handle_chat()`.
- `upload_dataset()` handles knowledge-base uploads and re-ingestion.

### `assistant.py`

Central orchestration layer for chat.

Responsibilities:

- Applies input guardrails before any business logic runs.
- Chooses between hotel Q&A and reservation handling.
- Retrieves RAG context for hotel-information questions.
- Calls the LLM abstraction layer.
- Generates a deterministic fallback answer when the provider fails.

Key functions:

- `handle_chat(query)` is the top-level chat router.
- `_handle_reservation(query)` dispatches reservation create, view, and cancel flows.
- `_build_fallback_answer(question, context)` produces a local answer when no external LLM response is available.
- `create_reservation_from_api(payload)` adapts reservation creation for the REST API response contract.

### `config.py`

Centralized application settings using `pydantic-settings`.

Responsibilities:

- Loads environment variables from `.env`.
- Defines provider-specific settings for OpenAI, Hugging Face, and Ollama.
- Stores RAG chunking and retrieval configuration.
- Stores file paths and database connection information.
- Normalizes the configured LLM provider choice.

Important settings:

- `LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `HF_API_KEY`
- `HF_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `PDF_PATH`
- `DATABASE_URL`
- `CHUNK_SIZE`
- `TOP_K`

### `database/models.py`

Persistence layer.

Responsibilities:

- Defines the SQLAlchemy base model.
- Defines the `Reservation` table schema.
- Creates the engine and session factory.
- Creates tables on startup.

Key symbols:

- `Reservation`
- `engine`
- `SessionLocal`
- `init_db()`

### `database/database.py`

Small compatibility module that re-exports:

- `SessionLocal`
- `init_db`

This keeps database imports simple in higher-level modules.

### `tools/reservation.py`

Reservation service layer.

Responsibilities:

- Validates reservation creation payloads with Pydantic.
- Creates reservations with UUID primary keys.
- Reads reservations by ID.
- Cancels reservations by updating status.
- Sanitizes returned reservation data to mask PII.

Key symbols:

- `ReservationCreate`
- `ReservationResponse`
- `create_reservation(payload)`
- `view_reservation(reservation_id)`
- `cancel_reservation(reservation_id)`
- `_to_response(reservation)`

### `router/intent_router.py`

Keyword-based routing logic.

Responsibilities:

- Detects whether a chat message is about reservations or hotel information.
- Infers the reservation action.
- Extracts a reservation UUID from free-form chat.

Key functions:

- `classify_intent(query)`
- `reservation_action(query)`
- `extract_reservation_id(query)`

### `guardrails/security.py`

Input safety and access-control heuristics.

Responsibilities:

- Blocks clearly off-topic questions.
- Blocks bulk access requests for other guests' reservations.
- Returns canned safety responses.

Key functions:

- `is_off_topic(query)`
- `is_bulk_access_request(query)`
- `off_topic_response()`
- `bulk_access_response()`

### `guardrails/pii.py`

Response sanitization layer.

Responsibilities:

- Masks email addresses before returning reservation data.
- Masks phone numbers before returning reservation data.

Key functions:

- `mask_email(email)`
- `mask_phone(phone)`
- `sanitize_reservation_for_response(data)`

### `rag/ingest.py`

Knowledge ingestion and retrieval storage.

Responsibilities:

- Reads PDF content using `pypdf`.
- Splits hotel-guide text into chunks.
- Normalizes and stores chunks in an in-memory index.
- Builds a lightweight vector-like collection using token counts and cosine similarity.
- Provides a lexical fallback retrieval strategy.
- Reports the active storage mode.

Important implementation details:

- `_SIMPLE_INDEX` stores normalized chunks keyed by collection name.
- `_VECTOR_COLLECTION` stores the in-memory retrieval object when available.
- The current implementation does not persist vectors to an external vector database.
- Although `chromadb` appears in dependencies, the active retrieval logic is custom and in-memory.

Key functions and classes:

- `_SimpleVectorCollection`
- `_tokenize(text)`
- `_cosine_similarity(query_vector, chunk_vector)`
- `_load_pdf_text(pdf_path)`
- `_split_text(text)`
- `ingest_pdf(force=False)`
- `ingest_text(text, force=False)`
- `build_rag_context(query, top_k=4)`
- `get_collection()`
- `get_storage_mode()`

### `rag/retriever.py`

Thin retrieval wrapper.

Responsibilities:

- Queries the active retrieval collection for the top matching chunks.
- Falls back to lexical retrieval if collection query fails.

Key function:

- `retrieve_context(query)`

### `rag/prompt.py`

Prompt constants for context-grounded Q&A.

Responsibilities:

- Defines the system prompt that forbids outside knowledge.
- Defines the user prompt template that injects context and question.
- Defines the shared "not found" message.

Key symbols:

- `RAG_SYSTEM_PROMPT`
- `RAG_USER_TEMPLATE`
- `NOT_FOUND_MESSAGE`

### `utils/llm.py`

LLM provider abstraction.

Responsibilities:

- Selects an LLM provider based on configuration.
- Calls OpenAI, Hugging Face Inference API, or Ollama.
- Returns a fallback answer when all providers fail.

Key symbols:

- `LLMClient`
- `generate_rag_answer(question, context)`
- `get_llm_client()`

### `utils/logger.py`

Application-wide logging setup.

Responsibilities:

- Configures root logging with a timestamped format.
- Exposes the `hotel-assistant` logger instance.

## Dependency Relationships

### Core Dependency Graph

```text
app.py
  ├── assistant.py
  ├── database.database
  ├── rag.ingest
  ├── tools.reservation
  └── utils.logger

assistant.py
  ├── guardrails.security
  ├── rag.prompt
  ├── rag.retriever
  ├── router.intent_router
  ├── tools.reservation
  └── utils.llm

utils.llm
  ├── config.py
  └── rag.prompt

rag.retriever
  ├── config.py
  └── rag.ingest

tools.reservation
  ├── database.models
  ├── guardrails.pii
  └── utils.logger

database.models
  └── config.py
```

### External Libraries

- `fastapi` provides the web API framework.
- `uvicorn` runs the ASGI app.
- `pydantic` and `pydantic-settings` validate payloads and configuration.
- `sqlalchemy` handles SQLite persistence.
- `pypdf` extracts text from hotel PDFs.
- `httpx` is used for Hugging Face and Ollama HTTP requests.
- `openai` is used for OpenAI chat completions.
- `email-validator` validates reservation email addresses.

### Notable Design Choices

- The application uses direct function calls instead of service containers or dependency injection frameworks.
- Intent routing is heuristic and keyword-based, not model-based.
- Retrieval is in-memory and rebuilt on startup or upload.
- Reservation data is masked before being returned, reducing accidental PII leakage.
- The chat path degrades gracefully to local fallback answers when LLM providers fail.

## Key Classes and Functions Reference

### API Layer

- `app.lifespan()`: startup initialization for database and RAG.
- `app.chat()`: main chat endpoint.
- `app.upload_dataset()`: replaces or augments the hotel knowledge source.
- `app.reservation_create()`: reservation creation endpoint.
- `app.reservation_view()`: reservation lookup endpoint.
- `app.reservation_cancel()`: reservation cancellation endpoint.

### Chat Orchestration

- `assistant.handle_chat()`: end-to-end chat request handling.
- `assistant._handle_reservation()`: free-text reservation workflow.
- `assistant._build_fallback_answer()`: deterministic local answer generation.

### Retrieval

- `rag.ingest.ingest_pdf()`: load the configured PDF and index it.
- `rag.ingest.ingest_text()`: ingest text directly.
- `rag.ingest.build_rag_context()`: lexical fallback retrieval.
- `rag.retriever.retrieve_context()`: fetch top matching context chunks.

### Reservation Services

- `tools.reservation.create_reservation()`: create and persist a reservation.
- `tools.reservation.view_reservation()`: load a reservation by ID.
- `tools.reservation.cancel_reservation()`: mark a reservation as cancelled.

### Infrastructure

- `database.models.init_db()`: create DB schema.
- `utils.llm.LLMClient.generate_rag_answer()`: ask the active LLM provider.
- `guardrails.pii.sanitize_reservation_for_response()`: mask sensitive fields.

## Runtime Configuration

The app is environment-driven. Place configuration in `.env`.

Recommended variables:

```env
LLM_PROVIDER=auto
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
HF_API_KEY=
HF_MODEL=microsoft/Phi-3.5-mini-instruct
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
PDF_PATH=data/hotel.pdf
DATABASE_URL=sqlite:///./hotel_reservations.db
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=3
```

Provider behavior:

- `LLM_PROVIDER=auto` lets the application choose the first configured provider that is available.
- `LLM_PROVIDER=openai` forces OpenAI usage.
- `LLM_PROVIDER=huggingface` forces Hugging Face usage.
- `LLM_PROVIDER=ollama` forces local Ollama usage.

## How To Run

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env`

Set at least one provider:

- OpenAI: set `OPENAI_API_KEY`
- Hugging Face: set `HF_API_KEY`
- Ollama: install Ollama locally and keep `OLLAMA_BASE_URL` reachable

### 4. Ensure the knowledge source exists

The default hotel guide path is:

```text
data/hotel.pdf
```

### 5. Start the API server

```bash
uvicorn app:app --reload
```

### 6. Open the API docs

```text
http://127.0.0.1:8000/docs
```

## Operational Notes

### Why hotel Q&A can still work when a provider fails

The chat pipeline retrieves context first, then asks the LLM provider for a grounded answer. If the provider call fails, `assistant.py` and `utils/llm.py` fall back to a local answer synthesized from the retrieved chunks.

### Why `GET /openapi.json` returning `200 OK` is normal

FastAPI serves OpenAPI metadata for Swagger UI and API tooling. That log line is not an error.

### Why `Stored 9 chunks in the vector store` is normal

That message comes from `rag/ingest.py` after the uploaded or startup PDF is successfully chunked and indexed.

### Why an OpenAI `429` happens

`429 Too Many Requests` indicates the upstream provider rejected the request because of quota, rate limit, or billing restrictions for the OpenAI project tied to the API key.

Typical causes:

- exhausted credits
- missing billing setup
- request bursts without retry/backoff
- a shared API key being used elsewhere

## Improvement Opportunities

- Add automated tests for chat routing, retrieval ranking, and reservation flows.
- Persist retrieval state instead of rebuilding the index on every startup.
- Replace keyword routing with structured intent parsing if the command surface expands.
- Add validation for reservation dates and room types.
- Add explicit provider health checks and richer error reporting for failed LLM calls.

## Summary

This repository uses a compact architecture:

- FastAPI for HTTP endpoints
- SQLAlchemy for reservation storage
- Custom in-memory retrieval for hotel-guide context
- Configurable LLM providers for grounded answer generation
- Simple guardrails for topic and privacy protection

That makes the project easy to understand, easy to run locally, and straightforward to extend.
