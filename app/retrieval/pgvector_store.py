from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.document import Document, DocumentChunk
from app.retrieval.splitter import split_documents_by_type
from app.retrieval.types import RetrievedChunk
from app.retrieval.vectorstore import get_embeddings


@dataclass(frozen=True)
class PgVectorRetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    distance: float | None = None

    def to_retrieved_chunk(self, *, rank: int | None = None) -> RetrievedChunk:
        return RetrievedChunk(
            rank=rank,
            content=self.content,
            source=self.filename,
            document_id=self.document_id,
            chunk_id=self.chunk_id,
            chunk_index=self.chunk_index,
            metadata=self.metadata,
            page=str(self.metadata["page"]) if self.metadata.get("page") is not None else None,
            score=self.distance,
        )

    def to_reference(self) -> dict[str, Any]:
        return self.to_retrieved_chunk().to_reference()


def retrieve_pgvector_retrieved_chunks(
    session: Session,
    *,
    user_id: int,
    kb_id: int,
    query: str,
    top_k: int,
    embeddings=None,
) -> list[RetrievedChunk]:
    return [
        chunk.to_retrieved_chunk(rank=rank)
        for rank, chunk in enumerate(
            retrieve_pgvector_chunks(
                session,
                user_id=user_id,
                kb_id=kb_id,
                query=query,
                top_k=top_k,
                embeddings=embeddings,
            ),
            start=1,
        )
    ]


def ingest_document_chunks(
    session: Session,
    *,
    document: Document,
    parsed_docs: list[LangChainDocument],
    embeddings=None,
) -> int:
    split_docs = _prepare_split_docs(document=document, parsed_docs=parsed_docs)
    texts = [doc.page_content for doc in split_docs]
    vectors = (embeddings or get_embeddings()).embed_documents(texts) if texts else []

    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    for index, (split_doc, embedding) in enumerate(zip(split_docs, vectors)):
        metadata = dict(split_doc.metadata or {})
        chunk = DocumentChunk(
            document_id=document.id,
            kb_id=document.kb_id,
            user_id=document.user_id,
            chunk_index=index,
            content=split_doc.page_content,
            embedding=embedding,
            chunk_metadata=metadata,
        )
        session.add(chunk)

    session.commit()
    return len(split_docs)


def retrieve_pgvector_chunks(
    session: Session,
    *,
    user_id: int,
    kb_id: int,
    query: str,
    top_k: int,
    embeddings=None,
) -> list[PgVectorRetrievedChunk]:
    query_embedding = (embeddings or get_embeddings()).embed_query(query)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(DocumentChunk, Document.filename, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.user_id == user_id, DocumentChunk.kb_id == kb_id)
        .order_by(distance)
        .limit(top_k)
    )

    results: list[PgVectorRetrievedChunk] = []
    for chunk, filename, score in session.execute(statement):
        results.append(
            PgVectorRetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=dict(chunk.chunk_metadata or {}),
                distance=float(score) if score is not None else None,
            )
        )
    return results


def _prepare_split_docs(*, document: Document, parsed_docs: list[LangChainDocument]) -> list[LangChainDocument]:
    normalized_docs: list[LangChainDocument] = []
    for parsed_doc in parsed_docs:
        metadata = dict(parsed_doc.metadata or {})
        metadata.setdefault("source", document.filename)
        metadata.setdefault("document_id", document.id)
        metadata.setdefault("kb_id", document.kb_id)
        metadata.setdefault("user_id", document.user_id)
        normalized_docs.append(LangChainDocument(page_content=parsed_doc.page_content, metadata=metadata))
    return split_documents_by_type(normalized_docs)
