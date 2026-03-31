from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.logging_setup import setup_logging
from app.config.settings import settings
from app.retrieval.vectorstore import get_vector_store

CHROMA_GET_BATCH_SIZE = 512
logger = logging.getLogger(__name__)


def load_documents(data_dir: str) -> list:
    docs = []
    root = Path(data_dir)

    if not root.exists():
        raise FileNotFoundError(f"Data directory not found: {root.resolve()}")

    for path in root.rglob("*"):
        if path.is_dir():
            continue

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            docs.extend(PyPDFLoader(str(path)).load())
        elif suffix in {".txt", ".md"}:
            docs.extend(TextLoader(str(path), encoding="utf-8").load())

    logger.info("原始文档加载完成。data_dir=%s 文档数=%s", root.resolve(), len(docs))
    return docs


def _normalize_source(source: str | None, data_root: Path) -> str:
    if not source:
        return ""

    source_path = Path(source).resolve()
    try:
        return source_path.relative_to(data_root.resolve()).as_posix()
    except ValueError:
        return source_path.as_posix()


def _prepare_chunk_ids(split_docs: list[Document], data_dir: str) -> list[Document]:
    data_root = Path(data_dir)
    chunk_indexes: dict[tuple[str, str], int] = {}
    unique_docs: dict[str, Document] = {}

    for doc in split_docs:
        metadata = dict(doc.metadata or {})
        source = _normalize_source(metadata.get("source"), data_root)
        page = str(metadata.get("page", "na"))
        chunk_key = (source, page)
        chunk_index = chunk_indexes.get(chunk_key, 0)
        chunk_indexes[chunk_key] = chunk_index + 1

        content_hash = hashlib.sha1(doc.page_content.encode("utf-8")).hexdigest()
        stable_key = f"{source}|{page}|{chunk_index}|{content_hash}"
        chunk_id = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()

        metadata["source"] = source or metadata.get("source", "")
        metadata["chunk_index"] = chunk_index
        metadata["content_hash"] = content_hash

        unique_docs.setdefault(
            chunk_id,
            Document(
                id=chunk_id,
                page_content=doc.page_content,
                metadata=metadata,
            ),
        )

    return list(unique_docs.values())


def _get_existing_ids(vector_store, ids: list[str]) -> set[str]:
    existing_ids: set[str] = set()

    for start in range(0, len(ids), CHROMA_GET_BATCH_SIZE):
        batch_ids = ids[start : start + CHROMA_GET_BATCH_SIZE]
        if not batch_ids:
            continue

        result = vector_store.get(ids=batch_ids, include=[])
        existing_ids.update(result.get("ids", []))

    return existing_ids


def ingest_documents(data_dir: str) -> int:
    setup_logging()
    logger.info("开始执行入库。data_dir=%s", Path(data_dir).resolve())
    raw_docs = load_documents(data_dir)
    if not raw_docs:
        logger.info("没有可入库的文档。data_dir=%s", Path(data_dir).resolve())
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    split_docs = splitter.split_documents(raw_docs)
    prepared_docs = _prepare_chunk_ids(split_docs, data_dir)
    logger.info(
        "切分并生成 chunk 完成。raw_docs=%s split_docs=%s unique_chunks=%s",
        len(raw_docs),
        len(split_docs),
        len(prepared_docs),
    )

    vector_store = get_vector_store()
    existing_ids = _get_existing_ids(
        vector_store,
        [doc.id for doc in prepared_docs if doc.id],
    )
    new_docs = [doc for doc in prepared_docs if doc.id not in existing_ids]
    logger.info(
        "入库去重完成。existing=%s new=%s",
        len(existing_ids),
        len(new_docs),
    )

    if not new_docs:
        logger.info("跳过入库，所有 chunk 都已存在。")
        return 0

    vector_store.add_documents(new_docs)
    logger.info("入库完成。inserted_chunks=%s", len(new_docs))
    return len(new_docs)


if __name__ == "__main__":
    count = ingest_documents("./data/raw")
    print(f"Ingested {count} chunks.")
