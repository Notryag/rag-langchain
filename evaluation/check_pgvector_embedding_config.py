from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from app.config.settings import settings
from app.db.session import get_session_factory
from app.retrieval.vectorstore import get_embeddings


@dataclass(frozen=True)
class PgVectorEmbeddingCheck:
    embedding_model: str
    configured_dimension: int
    database_dimension: int | None
    actual_dimension: int | None
    chunk_count: int
    ok: bool
    issues: list[str]


def check_pgvector_embedding_config(*, probe_model: bool = False) -> PgVectorEmbeddingCheck:
    database_dimension = _get_database_embedding_dimension()
    chunk_count = _get_chunk_count()
    actual_dimension = _get_actual_embedding_dimension() if probe_model else None
    issues = _collect_issues(
        configured_dimension=settings.embedding_dimension,
        database_dimension=database_dimension,
        actual_dimension=actual_dimension,
    )
    return PgVectorEmbeddingCheck(
        embedding_model=settings.embedding_model,
        configured_dimension=settings.embedding_dimension,
        database_dimension=database_dimension,
        actual_dimension=actual_dimension,
        chunk_count=chunk_count,
        ok=not issues,
        issues=issues,
    )


def _collect_issues(
    *,
    configured_dimension: int,
    database_dimension: int | None,
    actual_dimension: int | None,
) -> list[str]:
    issues: list[str] = []
    if database_dimension is None:
        issues.append("Could not detect document_chunks.embedding vector dimension.")
    elif database_dimension != configured_dimension:
        issues.append(
            f"Database vector dimension {database_dimension} does not match EMBEDDING_DIMENSION {configured_dimension}."
        )

    if actual_dimension is not None and actual_dimension != configured_dimension:
        issues.append(
            f"Actual embedding model output dimension {actual_dimension} does not match EMBEDDING_DIMENSION {configured_dimension}."
        )
    return issues


def _get_database_embedding_dimension() -> int | None:
    statement = text(
        """
        select atttypmod
        from pg_attribute
        where attrelid = 'document_chunks'::regclass
          and attname = 'embedding'
          and not attisdropped
        """
    )
    with get_session_factory()() as session:
        typmod = session.scalar(statement)
    if typmod is None or typmod < 0:
        return None
    return int(typmod)


def _get_chunk_count() -> int:
    with get_session_factory()() as session:
        return int(session.scalar(text("select count(*) from document_chunks")) or 0)


def _get_actual_embedding_dimension() -> int:
    vector = get_embeddings().embed_query("dimension check")
    return len(vector)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pgvector embedding dimension configuration.")
    parser.add_argument(
        "--probe-model",
        action="store_true",
        help="Call the embedding model and compare its real output dimension.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def _print_human(check: PgVectorEmbeddingCheck) -> None:
    print(f"embedding_model={check.embedding_model}")
    print(f"configured_dimension={check.configured_dimension}")
    print(f"database_dimension={check.database_dimension}")
    print(f"actual_dimension={check.actual_dimension}")
    print(f"chunk_count={check.chunk_count}")
    print(f"ok={str(check.ok).lower()}")
    for issue in check.issues:
        print(f"issue={issue}")


def main() -> None:
    args = _parse_args()
    check = check_pgvector_embedding_config(probe_model=args.probe_model)
    if args.json:
        print(json.dumps(asdict(check), ensure_ascii=False, indent=2))
        return
    _print_human(check)


if __name__ == "__main__":
    main()
