from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

_SUPPORTED_RETRIEVAL_SEARCH_TYPES = {"similarity", "mmr", "hybrid"}
_SUPPORTED_RERANKER_STRATEGIES = {"embedding_lexical"}
_SUPPORTED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _get_required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_optional_env(name: str) -> str | None:
    value = (os.getenv(name) or "").strip()
    return value or None


def _get_int_env(name: str, default: int) -> int:
    raw_value = (os.getenv(name) or "").strip()
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got: {raw_value}") from exc


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = (os.getenv(name) or "").strip().lower()
    if not raw_value:
        return default

    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean, got: {raw_value}")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str | None
    chat_model: str
    embedding_model: str
    vector_db_dir: str
    collection_name: str
    top_k: int
    retrieval_search_type: str
    retrieval_fetch_k: int
    reranker_enabled: bool
    reranker_strategy: str
    retrieval_max_context_chars: int
    chunk_size: int
    chunk_overlap: int
    log_dir: str
    log_level: str
    log_file_name: str

    def __post_init__(self) -> None:
        if self.retrieval_search_type not in _SUPPORTED_RETRIEVAL_SEARCH_TYPES:
            supported = ", ".join(sorted(_SUPPORTED_RETRIEVAL_SEARCH_TYPES))
            raise ValueError(
                f"RETRIEVAL_SEARCH_TYPE must be one of [{supported}], got: {self.retrieval_search_type}"
            )

        if self.reranker_strategy not in _SUPPORTED_RERANKER_STRATEGIES:
            supported = ", ".join(sorted(_SUPPORTED_RERANKER_STRATEGIES))
            raise ValueError(f"RERANKER_STRATEGY must be one of [{supported}], got: {self.reranker_strategy}")

        if self.log_level not in _SUPPORTED_LOG_LEVELS:
            supported = ", ".join(sorted(_SUPPORTED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of [{supported}], got: {self.log_level}")

        positive_fields = {
            "TOP_K": self.top_k,
            "RETRIEVAL_FETCH_K": self.retrieval_fetch_k,
            "RETRIEVAL_MAX_CONTEXT_CHARS": self.retrieval_max_context_chars,
            "CHUNK_SIZE": self.chunk_size,
        }
        for field_name, field_value in positive_fields.items():
            if field_value <= 0:
                raise ValueError(f"{field_name} must be > 0, got: {field_value}")

        if self.chunk_overlap < 0:
            raise ValueError(f"CHUNK_OVERLAP must be >= 0, got: {self.chunk_overlap}")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"CHUNK_OVERLAP must be smaller than CHUNK_SIZE, got overlap={self.chunk_overlap} size={self.chunk_size}"
            )

        if self.retrieval_fetch_k < self.top_k:
            raise ValueError(
                f"RETRIEVAL_FETCH_K must be >= TOP_K, got fetch_k={self.retrieval_fetch_k} top_k={self.top_k}"
            )

        required_string_fields = {
            "CHAT_MODEL": self.chat_model,
            "EMBEDDING_MODEL": self.embedding_model,
            "VECTOR_DB_DIR": self.vector_db_dir,
            "COLLECTION_NAME": self.collection_name,
            "LOG_DIR": self.log_dir,
            "LOG_FILE_NAME": self.log_file_name,
        }
        for field_name, field_value in required_string_fields.items():
            if not field_value.strip():
                raise ValueError(f"{field_name} must not be empty")

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            openai_api_key=_get_required_env("OPENAI_API_KEY"),
            openai_base_url=_get_optional_env("OPENAI_BASE_URL"),
            chat_model=(os.getenv("CHAT_MODEL") or "gpt-4.1-mini").strip(),
            embedding_model=(os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small").strip(),
            vector_db_dir=(os.getenv("VECTOR_DB_DIR") or "./storage/chroma").strip(),
            collection_name=(os.getenv("COLLECTION_NAME") or "rag_docs").strip(),
            top_k=_get_int_env("TOP_K", 3),
            retrieval_search_type=(os.getenv("RETRIEVAL_SEARCH_TYPE") or "similarity").strip().lower(),
            retrieval_fetch_k=_get_int_env("RETRIEVAL_FETCH_K", 8),
            reranker_enabled=_get_bool_env("RERANKER_ENABLED", False),
            reranker_strategy=(os.getenv("RERANKER_STRATEGY") or "embedding_lexical").strip().lower(),
            retrieval_max_context_chars=_get_int_env("RETRIEVAL_MAX_CONTEXT_CHARS", 4000),
            chunk_size=_get_int_env("CHUNK_SIZE", 800),
            chunk_overlap=_get_int_env("CHUNK_OVERLAP", 120),
            log_dir=(os.getenv("LOG_DIR") or "./logs").strip(),
            log_level=(os.getenv("LOG_LEVEL") or "INFO").strip().upper(),
            log_file_name=(os.getenv("LOG_FILE_NAME") or "app.log").strip(),
        )


settings = Settings.load()


if __name__ == "__main__":
    print(settings)
