from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_documents(data_dir: str) -> list[Document]:
    docs: list[Document] = []
    root = Path(data_dir)

    if not root.exists():
        raise FileNotFoundError(f"Data directory not found: {root.resolve()}")

    for path in root.rglob("*"):
        if path.is_dir():
            continue

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            docs.extend(PyPDFLoader(str(path)).load())
            continue

        if suffix in {".txt", ".md"}:
            docs.extend(TextLoader(str(path), encoding="utf-8").load())

    logger.info("原始文档加载完成。data_dir=%s 文档数=%s", root.resolve(), len(docs))
    return docs
