from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from langchain_core.documents import Document as LangChainDocument
from langchain_core.vectorstores.utils import maximal_marginal_relevance
from sqlalchemy import case, delete, func, literal, or_, select
from sqlalchemy.orm import Session

from app.db.models.document import Document, DocumentChunk
from app.config.settings import settings
from app.retrieval.lexical import query_terms
from app.retrieval.reranker import rerank_documents
from app.retrieval.splitter import split_documents_by_type
from app.retrieval.types import RetrievedChunk
from app.retrieval.embeddings import get_embeddings

DEFAULT_RRF_K = 60
MAX_LEXICAL_QUERY_TERMS = 32


@dataclass(frozen=True)
class PgVectorRetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    distance: float | None = None
    embedding: list[float] | None = None

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
    search_type: str = "similarity",
    fetch_k: int | None = None,
    reranker_enabled: bool = False,
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
                search_type=search_type,
                fetch_k=fetch_k,
                reranker_enabled=reranker_enabled,
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
    search_type: str = "similarity",
    fetch_k: int | None = None,
    reranker_enabled: bool = False,
    embeddings=None,
) -> list[PgVectorRetrievedChunk]:
    normalized_search_type = search_type.strip().lower()
    if normalized_search_type == "hybrid":
        candidate_k = max(fetch_k or top_k, top_k) if reranker_enabled else top_k
        chunks = retrieve_pgvector_hybrid_chunks(
            session,
            user_id=user_id,
            kb_id=kb_id,
            query=query,
            top_k=candidate_k,
            fetch_k=fetch_k,
            embeddings=embeddings,
        )
        return rerank_pgvector_chunks(query, chunks, top_k=top_k) if reranker_enabled else chunks[:top_k]
    if normalized_search_type not in {"similarity", "mmr"}:
        raise ValueError(f"Unsupported pgvector search_type: {search_type}")

    candidate_k = max(fetch_k or top_k, top_k) if normalized_search_type == "mmr" or reranker_enabled else top_k
    query_embedding = (embeddings or get_embeddings()).embed_query(query)
    _validate_embedding_dimension(query_embedding)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(DocumentChunk, Document.filename, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.user_id == user_id, DocumentChunk.kb_id == kb_id)
        .order_by(distance)
        .limit(candidate_k)
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
                embedding=getattr(chunk, "embedding", None) if normalized_search_type == "mmr" else None,
            )
        )
    if normalized_search_type == "mmr":
        results = _maximal_marginal_relevance_chunks(query_embedding, results, top_k=top_k)
    return rerank_pgvector_chunks(query, results, top_k=top_k) if reranker_enabled else results[:top_k]


def _maximal_marginal_relevance_chunks(
    query_embedding: list[float],
    chunks: list[PgVectorRetrievedChunk],
    *,
    top_k: int,
) -> list[PgVectorRetrievedChunk]:
    chunks_with_embeddings = [(chunk, chunk.embedding) for chunk in chunks if chunk.embedding is not None]
    if not chunks_with_embeddings:
        return []

    selected_indices = maximal_marginal_relevance(
        np.asarray(query_embedding, dtype=float),
        [embedding for _, embedding in chunks_with_embeddings],
        k=top_k,
    )
    return [chunks_with_embeddings[index][0] for index in selected_indices]


def retrieve_pgvector_lexical_chunks(
    session: Session,
    *,
    user_id: int,
    kb_id: int,
    query: str,
    top_k: int,
) -> list[PgVectorRetrievedChunk]:
    searchable_terms = [term for term in query_terms(query) if len(term) >= 3][:MAX_LEXICAL_QUERY_TERMS]
    if not searchable_terms:
        return []

    matches = [DocumentChunk.content.ilike(f"%{_escape_like(term)}%", escape="\\") for term in searchable_terms]
    lexical_score = sum(
        (case((match, 2), else_=0) for match in matches),
        start=literal(0),
    ).label("lexical_score")
    statement = (
        select(DocumentChunk, Document.filename, lexical_score)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.user_id == user_id,
            DocumentChunk.kb_id == kb_id,
            or_(*matches),
        )
        .order_by(lexical_score.desc(), func.length(DocumentChunk.content), DocumentChunk.id)
        .limit(top_k)
    )

    results: list[PgVectorRetrievedChunk] = []
    for chunk, filename, score in session.execute(statement):
        metadata = dict(chunk.chunk_metadata or {})
        results.append(
            PgVectorRetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata={**metadata, "lexical_score": int(score)},
                distance=None,
            )
        )

    return results


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def retrieve_pgvector_hybrid_chunks(
    session: Session,
    *,
    user_id: int,
    kb_id: int,
    query: str,
    top_k: int,
    fetch_k: int | None = None,
    embeddings=None,
) -> list[PgVectorRetrievedChunk]:
    candidate_k = max(fetch_k or top_k, top_k)
    dense_chunks = retrieve_pgvector_chunks(
        session,
        user_id=user_id,
        kb_id=kb_id,
        query=query,
        top_k=candidate_k,
        search_type="similarity",
        embeddings=embeddings,
    )
    lexical_chunks = retrieve_pgvector_lexical_chunks(
        session,
        user_id=user_id,
        kb_id=kb_id,
        query=query,
        top_k=candidate_k,
    )
    return _rrf_fuse_pgvector_chunks(dense_chunks, lexical_chunks, top_k=top_k)


def _rrf_fuse_pgvector_chunks(
    dense_chunks: list[PgVectorRetrievedChunk],
    lexical_chunks: list[PgVectorRetrievedChunk],
    *,
    top_k: int,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[PgVectorRetrievedChunk]:
    scores: dict[tuple[Any, ...], float] = {}
    chunks_by_key: dict[tuple[Any, ...], PgVectorRetrievedChunk] = {}

    for rank, chunk in enumerate(dense_chunks, start=1):
        key = _pgvector_chunk_key(chunk)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
        chunks_by_key.setdefault(key, chunk)

    for rank, chunk in enumerate(lexical_chunks, start=1):
        key = _pgvector_chunk_key(chunk)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
        chunks_by_key.setdefault(key, chunk)

    ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [chunks_by_key[key] for key in ranked_keys[:top_k]]


def _pgvector_chunk_key(chunk: PgVectorRetrievedChunk) -> tuple[Any, ...]:
    return (chunk.chunk_id, chunk.document_id, chunk.chunk_index)


def rerank_pgvector_chunks(
    query: str,
    chunks: list[PgVectorRetrievedChunk],
    *,
    top_k: int,
) -> list[PgVectorRetrievedChunk]:
    if not chunks:
        return []

    docs = [
        LangChainDocument(
            page_content=chunk.content,
            metadata={
                **chunk.metadata,
                "source": chunk.filename,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk in chunks
    ]
    reranked_docs = rerank_documents(query, docs, top_k=top_k)
    chunk_by_key = {(chunk.document_id, chunk.chunk_index): chunk for chunk in chunks}
    return [
        chunk_by_key[(doc.metadata["document_id"], doc.metadata["chunk_index"])]
        for doc in reranked_docs
    ]


def _validate_embedding_dimension(vector: list[float]) -> None:
    actual_dimension = len(vector)
    if actual_dimension != settings.embedding_dimension:
        raise ValueError(
            "Embedding dimension mismatch: "
            f"EMBEDDING_DIMENSION={settings.embedding_dimension}, actual={actual_dimension}. "
            "Update EMBEDDING_DIMENSION to match the embedding model output and rebuild pgvector embeddings."
        )


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
