from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from rag.ingest import get_collection, get_storage_mode, ingest_pdf, ingest_text

from assistant import create_reservation_from_api, handle_chat
from database.database import init_db
from rag.ingest import ingest_pdf
from tools.reservation import ReservationCreate, cancel_reservation, list_reservations, view_reservation
from utils.logger import logger


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        ingest_pdf()
    except Exception as exc:
        logger.warning("RAG ingest skipped at startup: %s", exc)
    logger.info("Hotel assistant started")
    yield


app = FastAPI(
    title="Hotel Reservation Assistant",
    description="RAG-powered hotel Q&A with reservation tools",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    started_at = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = (perf_counter() - started_at) * 1000
        status_code = response.status_code if response is not None else 500
        logger.info(
            "API %s %s -> %s in %.2f ms",
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
        )


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    intent: str
    response: str
    action: str | None = None
    reservation: dict | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = handle_chat(request.query)
    return ChatResponse(**result)


@app.post("/reservation/create")
def reservation_create(payload: ReservationCreate) -> dict:
    return create_reservation_from_api(payload)


@app.post("/upload")
def upload_dataset(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please upload a file")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        target_path = Path("data/hotel.pdf")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        try:
            ingest_pdf(force=False)
            return {
                "message": "PDF uploaded and ingested successfully.",
                "vector_store_ready": get_storage_mode() == "vector_store",
                "storage_mode": get_storage_mode(),
            }
        except Exception as exc:
            logger.warning("PDF upload completed but ingestion failed: %s", exc)
            return {"message": "PDF uploaded successfully, but ingestion failed.", "error": str(exc)}

    if filename.endswith((".txt", ".md", ".json")):
        try:
            text = data.decode("utf-8")
            ingest_text(text, force=True)
            return {
                "message": "Text dataset uploaded and ingested successfully.",
                "vector_store_ready": get_storage_mode() == "vector_store",
                "storage_mode": get_storage_mode(),
            }
        except Exception as exc:
            logger.warning("Text upload completed but ingestion failed: %s", exc)
            return {"message": "Text dataset uploaded successfully, but ingestion failed.", "error": str(exc)}

    raise HTTPException(status_code=400, detail="Supported formats: PDF, TXT, MD, or JSON")


@app.get("/reservation/{reservation_id}")
def reservation_view(reservation_id: str) -> dict:
    reservation = view_reservation(reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@app.get("/reservations")
def reservation_list() -> dict:
    reservations = list_reservations()
    return {
        "count": len(reservations),
        "reservations": reservations,
    }


@app.delete("/reservation/{reservation_id}")
def reservation_cancel(reservation_id: str) -> dict:
    reservation = cancel_reservation(reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {
        "message": f"Reservation {reservation_id} cancelled.",
        "reservation": reservation,
    }
