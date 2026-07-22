from config import settings
from rag.ingest import build_rag_context, get_collection


def retrieve_context(query: str) -> str:
    collection = get_collection()
    if collection is not None:
        try:
            results = collection.query(query_texts=[query], n_results=settings.top_k)
            documents = results.get("documents", [[]])[0]
            cleaned_documents = [" ".join(document.split()) for document in documents if document and " ".join(document.split())]
            if cleaned_documents:
                return "\n\n".join(cleaned_documents)
        except Exception:
            pass

    return build_rag_context(query, top_k=settings.top_k)
