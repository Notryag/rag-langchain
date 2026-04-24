from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _with_document_type(docs: list[Document], document_type: str) -> list[Document]:
    typed_docs: list[Document] = []
    for doc in docs:
        metadata = dict(doc.metadata or {})
        metadata["document_type"] = document_type
        typed_docs.append(
            Document(
                id=getattr(doc, "id", None),
                page_content=doc.page_content,
                metadata=metadata,
            )
        )
    return typed_docs


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
            docs.extend(_with_document_type(PyPDFLoader(str(path)).load(), "pdf"))
            continue

        if suffix == ".txt":
            docs.extend(_with_document_type(TextLoader(str(path), encoding="utf-8").load(), "text"))
            continue

        if suffix == ".md":
            docs.extend(_with_document_type(TextLoader(str(path), encoding="utf-8").load(), "markdown"))

    logger.info("原始文档加载完成。data_dir=%s 文档数=%s", root.resolve(), len(docs))
    return docs
