from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # Ignore unknown env variables
        case_sensitive=False,
    )

    # ------------------------
    # LLM Settings
    # ------------------------

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    openai_model: str = Field(
        default="gpt-4o-mini",
        alias="OPENAI_MODEL",
    )

    huggingface_api_key: str = Field(default="", validation_alias="HF_API_KEY")

    huggingface_model: str = Field(
        default="microsoft/Phi-3.5-mini-instruct",
        validation_alias="HF_MODEL",
    )

    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL",
    )

    ollama_model: str = Field(
        default="llama3.2",
        alias="OLLAMA_MODEL",
    )

    ollama_timeout_seconds: float = Field(
        default=120.0,
        alias="OLLAMA_TIMEOUT_SECONDS",
    )

    ollama_keep_alive: str = Field(
        default="10m",
        alias="OLLAMA_KEEP_ALIVE",
    )

    ollama_num_predict: int = Field(
        default=180,
        alias="OLLAMA_NUM_PREDICT",
    )

    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        alias="EMBEDDING_MODEL",
    )

    # ------------------------
    # Paths
    # ------------------------

    pdf_path: Path = Field(
        default=Path("data/hotel.pdf"),
        alias="PDF_PATH",
    )

    chroma_path: Path = Field(
        default=Path("chroma_db"),
        alias="CHROMA_PATH",
    )

    database_url: str = Field(
        default="sqlite:///./hotel_reservations.db",
        alias="DATABASE_URL",
    )

    # ------------------------
    # RAG
    # ------------------------

    chunk_size: int = Field(
        default=500,
        alias="CHUNK_SIZE",
    )

    chunk_overlap: int = Field(
        default=50,
        alias="CHUNK_OVERLAP",
    )

    top_k: int = Field(
        default=3,
        alias="TOP_K",
    )

    def model_post_init(self, __context: Any):
        provider = (self.llm_provider or "auto").strip().lower()
        if provider in {"hf", "huggingface", "huggingface-api"}:
            self.llm_provider = "huggingface"
        elif provider in {"ollama", "local"}:
            self.llm_provider = "ollama"
        elif provider in {"openai"}:
            self.llm_provider = "openai"
        else:
            self.llm_provider = "auto"

        self.pdf_path = self._resolve_path(self.pdf_path)
        self.chroma_path = self._resolve_path(self.chroma_path)
        self.database_url = self._resolve_database_url(self.database_url)

    @staticmethod
    def _resolve_path(path_value: Path) -> Path:
        if path_value.is_absolute():
            return path_value
        return (BASE_DIR / path_value).resolve()

    @staticmethod
    def _resolve_database_url(database_url: str) -> str:
        sqlite_prefix = "sqlite:///"
        if not database_url.startswith(sqlite_prefix):
            return database_url

        raw_path = database_url[len(sqlite_prefix):]
        if not raw_path or raw_path == ":memory:":
            return database_url

        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = (BASE_DIR / db_path).resolve()

        return f"{sqlite_prefix}{db_path.as_posix()}"


settings = Settings()
