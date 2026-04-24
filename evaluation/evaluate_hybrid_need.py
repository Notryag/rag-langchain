from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.config.logging_setup import setup_logging
from app.retrieval.normalizers import normalize_chunk_index, normalize_page
from app.retrieval.retriever import RetrievedChunk
from app.retrieval.vectorstore import get_vector_store
from evaluation.dataset import DEFAULT_RETRIEVAL_EVAL_PATH, RetrievalEvalSample, load_retrieval_eval_samples
from evaluation.evaluate_retrieval import RetrievalEvalConfig, evaluate_sample

DEFAULT_OUTPUT_PATH = Path("storage/exports/hybrid_need_eval.json")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*|[\u4e00-\u9fff]{2,}")


@dataclass(frozen=True)
class HybridNeedResult:
    sample: RetrievalEvalSample
    dense_passed: bool
    dense_source_hit: bool
    dense_sources: list[str]
    lexical_passed: bool
    lexical_source_hit: bool
    lexical_sources: list[str]
    lexical_matched_keywords: list[str]


def _load_index_chunks() -> list[RetrievedChunk]:
    vector_store = get_vector_store()
    raw = vector_store.get(include=["documents", "metadatas"])
    ids = raw.get("ids") or []
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []

    chunks: list[RetrievedChunk] = []
    for index, (doc_id, content, metadata) in enumerate(zip(ids, documents, metadatas, strict=False), start=1):
        doc = Document(
            id=doc_id,
            page_content=content or "",
            metadata=metadata or {},
        )
        chunks.append(RetrievedChunk.from_document(doc, rank=index))
    return chunks


def _query_terms(query: str) -> list[str]:
    terms = [match.group(0).lower() for match in _TOKEN_RE.finditer(query)]
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def _lexical_score(sample: RetrievalEvalSample, chunk: RetrievedChunk) -> tuple[int, list[str]]:
    content = chunk.content.lower()
    matched_keywords = [keyword for keyword in sample.expected_keywords if keyword.lower() in content]
    query_term_hits = sum(1 for term in _query_terms(sample.query) if term in content)
    source_term_hits = sum(1 for term in _query_terms(chunk.source) if term in sample.query.lower())
    score = len(matched_keywords) * 10 + query_term_hits + source_term_hits
    return score, matched_keywords


def _rank_lexical_chunks(sample: RetrievalEvalSample, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    scored: list[tuple[int, int, RetrievedChunk]] = []
    for chunk in chunks:
        score, _ = _lexical_score(sample, chunk)
        if score <= 0:
            continue
        scored.append((score, -len(chunk.content), chunk))

    ranked = [chunk for _, _, chunk in sorted(scored, key=lambda item: item[:2], reverse=True)]
    return [
        RetrievedChunk(
            rank=index,
            content=chunk.content,
            document_id=chunk.document_id,
            source=chunk.source,
            page=normalize_page(chunk.page),
            chunk_index=normalize_chunk_index(chunk.chunk_index),
            metadata=chunk.metadata,
        )
        for index, chunk in enumerate(ranked[:top_k], start=1)
    ]


def _match_keywords(sample: RetrievalEvalSample, chunks: list[RetrievedChunk]) -> list[str]:
    corpus = "\n".join(chunk.content.lower() for chunk in chunks)
    return [keyword for keyword in sample.expected_keywords if keyword.lower() in corpus]


def evaluate_hybrid_need(
    samples: list[RetrievalEvalSample],
    *,
    dense_config: RetrievalEvalConfig,
) -> list[HybridNeedResult]:
    index_chunks = _load_index_chunks()
    results: list[HybridNeedResult] = []

    for sample in samples:
        dense_result = evaluate_sample(sample, dense_config)
        if dense_result.skipped:
            continue

        lexical_chunks = _rank_lexical_chunks(sample, index_chunks, top_k=dense_config.top_k)
        lexical_hit_ranks = [chunk.rank for chunk in lexical_chunks if chunk.source in sample.expected_sources]
        lexical_matched_keywords = _match_keywords(sample, lexical_chunks)
        lexical_source_hit = bool(lexical_hit_ranks)
        lexical_passed = lexical_source_hit and len(lexical_matched_keywords) >= sample.expected_min_keyword_hits

        results.append(
            HybridNeedResult(
                sample=sample,
                dense_passed=dense_result.passed,
                dense_source_hit=dense_result.source_hit,
                dense_sources=[chunk.source for chunk in dense_result.chunks],
                lexical_passed=lexical_passed,
                lexical_source_hit=lexical_source_hit,
                lexical_sources=[chunk.source for chunk in lexical_chunks],
                lexical_matched_keywords=lexical_matched_keywords,
            )
        )

    return results


def _summarize(results: list[HybridNeedResult]) -> dict[str, int | float | str]:
    dense_passed = sum(1 for result in results if result.dense_passed)
    dense_failed = len(results) - dense_passed
    lexical_rescued = sum(1 for result in results if not result.dense_passed and result.lexical_passed)
    lexical_missed = sum(1 for result in results if not result.dense_passed and not result.lexical_passed)
    rescue_rate = round(lexical_rescued / dense_failed, 4) if dense_failed else 0.0
    recommendation = "evaluate_hybrid_search" if lexical_rescued > 0 else "prioritize_dataset_or_chunking_before_hybrid"
    return {
        "scored": len(results),
        "dense_passed": dense_passed,
        "dense_failed": dense_failed,
        "lexical_rescued_dense_failures": lexical_rescued,
        "lexical_missed_dense_failures": lexical_missed,
        "lexical_rescue_rate": rescue_rate,
        "recommendation": recommendation,
    }


def _result_to_dict(result: HybridNeedResult) -> dict[str, Any]:
    return {
        "id": result.sample.id,
        "query": result.sample.query,
        "category": result.sample.category,
        "expected_sources": result.sample.expected_sources,
        "dense_passed": result.dense_passed,
        "dense_source_hit": result.dense_source_hit,
        "dense_sources": result.dense_sources,
        "lexical_passed": result.lexical_passed,
        "lexical_source_hit": result.lexical_source_hit,
        "lexical_sources": result.lexical_sources,
        "lexical_matched_keywords": result.lexical_matched_keywords,
        "required_keyword_hits": result.sample.expected_min_keyword_hits,
    }


def _write_report(path: str | Path, summary: dict[str, Any], results: list[HybridNeedResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "dense_failures": [_result_to_dict(result) for result in results if not result.dense_passed],
    }
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose whether lexical/hybrid search is likely to help retrieval.")
    parser.add_argument("--dataset", default=str(DEFAULT_RETRIEVAL_EVAL_PATH), help="Path to retrieval eval jsonl.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to JSON diagnostic report.")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples.")
    parser.add_argument("--search-type", default="similarity", choices=["similarity", "mmr"], help="Dense baseline type.")
    parser.add_argument("--top-k", type=int, default=3, help="Top-k for dense and lexical diagnostics.")
    parser.add_argument("--fetch-k", type=int, default=8, help="Fetch-k for dense baseline.")
    parser.add_argument("--reranker", default="on", choices=["off", "on"], help="Dense baseline reranker mode.")
    parser.add_argument("--show-failures", action="store_true", help="Print dense failures and lexical diagnostic hits.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()
    samples = load_retrieval_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    dense_config = RetrievalEvalConfig(
        search_type=args.search_type,
        top_k=args.top_k,
        fetch_k=max(args.fetch_k, args.top_k),
        reranker_enabled=args.reranker == "on",
    )
    results = evaluate_hybrid_need(samples, dense_config=dense_config)
    summary = _summarize(results)
    _write_report(args.output, summary, results)

    print(
        "summary scored={scored} dense_passed={dense_passed} dense_failed={dense_failed} "
        "lexical_rescued_dense_failures={lexical_rescued_dense_failures} "
        "lexical_rescue_rate={lexical_rescue_rate:.2%} recommendation={recommendation}".format(**summary)
    )
    print(f"report_written={Path(args.output).as_posix()}")

    if args.show_failures:
        for result in results:
            if result.dense_passed:
                continue
            status = "LEXICAL_RESCUE" if result.lexical_passed else "MISS"
            print(f"[{status}] {result.sample.id} | {result.sample.query}")
            print(f"  dense_sources={result.dense_sources}")
            print(f"  lexical_sources={result.lexical_sources}")
            print(f"  lexical_keywords={result.lexical_matched_keywords}")


if __name__ == "__main__":
    main()
