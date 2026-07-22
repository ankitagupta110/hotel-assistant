import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from config import settings
from utils.logger import logger

COLLECTION_NAME = "hotel_guide"

_SIMPLE_INDEX: dict[str, list[str]] = {}
_VECTOR_COLLECTION: Any | None = None


class _SimpleVectorCollection:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.vocabulary = sorted({token for chunk in chunks for token in _tokenize(chunk)})
        self.vectors = [self._build_vector(chunk) for chunk in chunks]

    def _build_vector(self, chunk: str) -> Counter[str]:
        counts = Counter(_tokenize(chunk))
        return counts

    def query(self, query_texts: list[str], n_results: int = 4) -> dict[str, list[list[str]]]:
        if not self.chunks:
            return {"documents": [[]]}

        query_terms = _tokenize(" ".join(query_texts))
        if not query_terms:
            return {"documents": [[chunk for chunk in self.chunks[:n_results]]]} 

        query_vector = Counter(query_terms)
        scored_chunks: list[tuple[float, str]] = []
        for chunk, vector in zip(self.chunks, self.vectors):
            score = _cosine_similarity(query_vector, vector)
            if score > 0:
                scored_chunks.append((score, chunk))

        if not scored_chunks:
            return {"documents": [[chunk for chunk in self.chunks[:n_results]]]} 

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        ranked_chunks = [chunk for _, chunk in scored_chunks[:n_results]]
        return {"documents": [ranked_chunks]}


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def _cosine_similarity(query_vector: Counter[str], chunk_vector: Counter[str]) -> float:
    if not query_vector or not chunk_vector:
        return 0.0

    dot_product = sum(query_vector[token] * chunk_vector[token] for token in query_vector.keys() & chunk_vector.keys())
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    chunk_norm = math.sqrt(sum(value * value for value in chunk_vector.values()))
    if query_norm == 0 or chunk_norm == 0:
        return 0.0
    return dot_product / (query_norm * chunk_norm)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _load_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _split_text(text: str) -> list[str]:
    if not text.strip():
        return []

    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        if current and current_length + paragraph_length + 1 > settings.chunk_size:
            chunks.append("\n".join(current))
            current = [paragraph]
            current_length = paragraph_length
        else:
            current.append(paragraph)
            current_length += paragraph_length + 1

    if current:
        chunks.append("\n".join(current))

    return chunks


def ingest_pdf(force: bool = False) -> None:
    pdf_path = settings.pdf_path
    if not pdf_path.exists():
        raise FileNotFoundError(f"Hotel PDF not found at {pdf_path}")

    text = _load_pdf_text(pdf_path)
    ingest_text(text, force=force)


def ingest_text(text: str, force: bool = False) -> None:
    chunks = _split_text(text)
    if not chunks:
        raise ValueError("No text extracted from uploaded dataset")

    normalized_chunks = [_normalize_text(chunk) for chunk in chunks if _normalize_text(chunk)]
    _SIMPLE_INDEX.clear()
    _SIMPLE_INDEX[COLLECTION_NAME] = normalized_chunks

    global _VECTOR_COLLECTION
    _VECTOR_COLLECTION = None
    try:
        documents = [chunk for chunk in normalized_chunks if chunk]
        _VECTOR_COLLECTION = _SimpleVectorCollection(documents)
        logger.info("Stored %s chunks in the vector store", len(documents))
    except Exception as exc:
        logger.warning("Vector store unavailable, using fallback text index: %s", exc)
        _VECTOR_COLLECTION = None


def _score_chunk(query_terms: list[str], query_term_set: set[str], chunk: str) -> tuple[float, str]:
    chunk_lower = chunk.lower()
    chunk_terms = [term for term in re.split(r"[^a-z0-9]+", chunk_lower) if len(term) > 2]
    chunk_term_set = set(chunk_terms)

    overlap_score = sum(1 for term in query_term_set if term in chunk_term_set)
    lexical_score = 0.0
    for term in query_terms:
        if term in chunk_lower:
            term_count = chunk_lower.count(term)
            lexical_score += 1 + math.log(term_count)

    total_score = (overlap_score * 2.0) + lexical_score
    return total_score, chunk


def build_rag_context(query: str, top_k: int = 4) -> str:
    if _VECTOR_COLLECTION is not None:
        try:
            results = _VECTOR_COLLECTION.query([query], n_results=top_k)
            documents = results.get("documents", [[]])[0]
            cleaned_documents = [chunk.strip() for chunk in documents if chunk and chunk.strip()]
            if cleaned_documents:
                return "\n\n".join(cleaned_documents[:4])
        except Exception:
            pass

    query_terms = [term for term in re.split(r"[^a-z0-9]+", query.lower()) if len(term) > 2]
    query_term_set = set(query_terms)

    if not query_terms:
        return ""

    scored_chunks = []
    for chunk in _SIMPLE_INDEX.get(COLLECTION_NAME, []):
        score, text = _score_chunk(query_terms, query_term_set, chunk)
        if score > 0:
            scored_chunks.append((score, text))

    if not scored_chunks:
        return ""

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    ranked_chunks = [chunk for _, chunk in scored_chunks[:top_k]]

    deduped: list[str] = []
    seen: set[str] = set()
    for chunk in ranked_chunks:
        key = chunk.lower()
        if key not in seen:
            deduped.append(chunk)
            seen.add(key)

    return "\n\n".join(deduped[:4])


def get_collection() -> Any | None:
    class _FallbackCollection:
        def query(self, query_texts: list[str], n_results: int = 4) -> dict[str, list[list[str]]]:
            query = " ".join(query_texts)
            context = build_rag_context(query, top_k=n_results)
            if not context:
                return {"documents": [[]]}
            return {"documents": [[chunk.strip() for chunk in context.split("\n\n") if chunk.strip()]]}

    if _VECTOR_COLLECTION is not None:
        return _VECTOR_COLLECTION

    if not _SIMPLE_INDEX.get(COLLECTION_NAME):
        return None
    return _FallbackCollection()


def get_storage_mode() -> str:
    if _VECTOR_COLLECTION is not None:
        return "vector_store"
    return "fallback_text_index"
