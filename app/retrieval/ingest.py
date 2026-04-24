from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from langchain_core.documents import Document

from app.config.logging_setup import setup_logging
from app.retrieval.loaders import load_documents
from app.retrieval.splitter import split_documents_by_type
from app.retrieval.vectorstore import get_vector_store

CHROMA_GET_BATCH_SIZE = 512
logger = logging.getLogger(__name__)
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

    split_docs = split_documents_by_type(raw_docs)
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
