from __future__ import annotations

import hashlib
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Literal
from uuid import uuid4

from langchain_core.documents import Document

from app.config.logging_setup import setup_logging
from app.retrieval.loaders import load_documents
from app.retrieval.splitter import split_documents_by_type
from app.retrieval.vectorstore import get_vector_store

CHROMA_GET_BATCH_SIZE = 512
IngestMode = Literal["skip_existing", "rebuild"]

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


def _count_by_source(docs: list[Document]) -> dict[str, int]:
    return dict(Counter(str((doc.metadata or {}).get("source", "unknown")) for doc in docs))


def _reset_vector_store(vector_store) -> None:
    logger.warning("重建索引模式已启用，将清空当前 collection 后重新入库。")
    vector_store.reset_collection()


def _select_documents_to_insert(
    vector_store,
    prepared_docs: list[Document],
    *,
    mode: IngestMode,
    run_id: str,
) -> list[Document]:
    if mode == "rebuild":
        _reset_vector_store(vector_store)
        logger.info("重建索引模式跳过去重检查。run_id=%s new=%s", run_id, len(prepared_docs))
        return prepared_docs

    existing_ids = _get_existing_ids(
        vector_store,
        [doc.id for doc in prepared_docs if doc.id],
    )
    new_docs = [doc for doc in prepared_docs if doc.id not in existing_ids]
    logger.info(
        "增量入库去重完成。run_id=%s existing=%s new=%s new_by_source=%s",
        run_id,
        len(existing_ids),
        len(new_docs),
        _count_by_source(new_docs),
    )
    return new_docs


def ingest_documents(data_dir: str, *, mode: IngestMode = "skip_existing") -> int:
    setup_logging()
    if mode not in ("skip_existing", "rebuild"):
        raise ValueError(f"Unsupported ingest mode: {mode}")

    started_at = time.perf_counter()
    run_id = uuid4().hex[:8]
    resolved_data_dir = Path(data_dir).resolve()
    logger.info("开始执行入库。run_id=%s data_dir=%s mode=%s", run_id, resolved_data_dir, mode)
    raw_docs = load_documents(data_dir)
    if not raw_docs:
        logger.info("没有可入库的文档。run_id=%s data_dir=%s", run_id, resolved_data_dir)
        return 0

    logger.info("原始文档统计。run_id=%s raw_docs=%s raw_by_source=%s", run_id, len(raw_docs), _count_by_source(raw_docs))
    split_docs = split_documents_by_type(raw_docs)
    prepared_docs = _prepare_chunk_ids(split_docs, data_dir)
    logger.info(
        "切分并生成 chunk 完成。run_id=%s raw_docs=%s split_docs=%s unique_chunks=%s split_by_source=%s unique_by_source=%s",
        run_id,
        len(raw_docs),
        len(split_docs),
        len(prepared_docs),
        _count_by_source(split_docs),
        _count_by_source(prepared_docs),
    )

    vector_store = get_vector_store()
    new_docs = _select_documents_to_insert(vector_store, prepared_docs, mode=mode, run_id=run_id)

    if not new_docs:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("跳过入库，所有 chunk 都已存在。run_id=%s elapsed_ms=%s", run_id, elapsed_ms)
        return 0

    vector_store.add_documents(new_docs)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "入库完成。run_id=%s mode=%s inserted_chunks=%s inserted_by_source=%s elapsed_ms=%s",
        run_id,
        mode,
        len(new_docs),
        _count_by_source(new_docs),
        elapsed_ms,
    )
    return len(new_docs)


if __name__ == "__main__":
    count = ingest_documents("./data/raw")
    print(f"Ingested {count} chunks.")
