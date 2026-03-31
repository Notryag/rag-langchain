
from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()

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
    chunk_size: int
    chunk_overlap: int
    log_dir: str
    log_level: str
    log_file_name: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            chat_model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            vector_db_dir=os.getenv("VECTOR_DB_DIR", "./storage/chroma"),
            collection_name=os.getenv("COLLECTION_NAME", "rag_docs"),
            top_k=int(os.getenv("TOP_K", "3")),
            retrieval_search_type=os.getenv("RETRIEVAL_SEARCH_TYPE", "similarity").lower(),
            retrieval_fetch_k=int(os.getenv("RETRIEVAL_FETCH_K", "8")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
            log_dir=os.getenv("LOG_DIR", "./logs"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_file_name=os.getenv("LOG_FILE_NAME", "app.log"),
        )
    
settings = Settings.load()



if __name__ == '__main__':
    print(settings)
