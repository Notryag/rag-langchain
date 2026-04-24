from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.logging_setup import setup_logging
from app.retrieval.normalizers import normalize_chunk_index, normalize_page
from app.retrieval.retriever import RetrievedChunk, retrieve_chunks
from evaluation.dataset import DEFAULT_RETRIEVAL_EVAL_PATH, RetrievalEvalSample, load_retrieval_eval_samples
from evaluation.evaluate_hybrid_need import _load_index_chunks
from evaluation.evaluate_retrieval import RetrievalEvalConfig, RetrievalEvalResult, evaluate_sample

DEFAULT_OUTPUT_PATH = Path("storage/exports/hybrid_search_eval.json")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")
_CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_STOP_TERMS = {
    "一下",
    "一直",
    "一般",
    "什么",
    "使用",
    "先做",
    "应该",
    "怎么",
    "怎样",
    "情况",
    "时候",
    "机器人",
    "扫地",
    "需要",
    "这种",
}


@dataclass(frozen=True)
class HybridEvalResult:
    sample: RetrievalEvalSample
    baseline: RetrievalEvalResult
    hybrid_passed: bool
    hybrid_source_hit: bool
    hybrid_hit_ranks: list[int]
    hybrid_matched_keywords: list[str]
    hybrid_chunks: list[RetrievedChunk]
    dense_sources: list[str]
    lexical_sources: list[str]


def _chunk_key(chunk: RetrievedChunk) -> tuple[Any, ...]:
    content_hash = chunk.metadata.get("content_hash")
    if content_hash:
        return ("content_hash", content_hash)
    return (chunk.document_id, chunk.source, chunk.page, chunk.chunk_index)


def _chinese_ngrams(text: str) -> list[str]:
    terms: list[str] = []
    for match in _CHINESE_RUN_RE.finditer(text):
        run = match.group(0)
        for size in (2, 3, 4):
            if len(run) < size:
                continue
            terms.extend(run[index : index + size] for index in range(0, len(run) - size + 1))
    return terms


def _query_terms(query: str) -> list[str]:
    terms = [match.group(0).lower() for match in _LATIN_TOKEN_RE.finditer(query)]
    terms.extend(term.lower() for term in _chinese_ngrams(query))
    deduped = list(dict.fromkeys(term for term in terms if term not in _STOP_TERMS))
    return deduped


def _lexical_score(query: str, chunk: RetrievedChunk) -> int:
    content = chunk.content.lower()
    score = 0
    for term in _query_terms(query):
        if term in content:
            score += 2 if len(term) >= 3 else 1
    return score


def _rank_lexical_chunks(query: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    scored: list[tuple[int, int, RetrievedChunk]] = []
    for chunk in chunks:
        score = _lexical_score(query, chunk)
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


def _rrf_fuse(
    dense_chunks: list[RetrievedChunk],
    lexical_chunks: list[RetrievedChunk],
    *,
    top_k: int,
    rrf_k: int,
    lexical_weight: float,
) -> list[RetrievedChunk]:
    scores: dict[tuple[Any, ...], float] = {}
    chunks_by_key: dict[tuple[Any, ...], RetrievedChunk] = {}

    for rank, chunk in enumerate(dense_chunks, start=1):
        key = _chunk_key(chunk)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
        chunks_by_key.setdefault(key, chunk)

    for rank, chunk in enumerate(lexical_chunks, start=1):
        key = _chunk_key(chunk)
        scores[key] = scores.get(key, 0.0) + lexical_weight / (rrf_k + rank)
        chunks_by_key.setdefault(key, chunk)

    ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
    fused: list[RetrievedChunk] = []
    for index, key in enumerate(ranked_keys[:top_k], start=1):
        chunk = chunks_by_key[key]
        fused.append(
            RetrievedChunk(
                rank=index,
                content=chunk.content,
                document_id=chunk.document_id,
                source=chunk.source,
                page=chunk.page,
                chunk_index=chunk.chunk_index,
                metadata=chunk.metadata,
            )
        )
    return fused


def _match_keywords(sample: RetrievalEvalSample, chunks: list[RetrievedChunk]) -> list[str]:
    corpus = "\n".join(chunk.content.lower() for chunk in chunks)
    return [keyword for keyword in sample.expected_keywords if keyword.lower() in corpus]


def _evaluate_hybrid_chunks(sample: RetrievalEvalSample, chunks: list[RetrievedChunk]) -> tuple[bool, bool, list[int], list[str]]:
    hit_ranks = [chunk.rank for chunk in chunks if chunk.source in sample.expected_sources]
    matched_keywords = _match_keywords(sample, chunks)
    source_hit = bool(hit_ranks)
    passed = source_hit and len(matched_keywords) >= sample.expected_min_keyword_hits
    return passed, source_hit, hit_ranks, matched_keywords


def evaluate_hybrid_search(
    samples: list[RetrievalEvalSample],
    *,
    baseline_config: RetrievalEvalConfig,
    dense_k: int,
    lexical_k: int,
    rrf_k: int,
    lexical_weight: float,
) -> list[HybridEvalResult]:
    index_chunks = _load_index_chunks()
    results: list[HybridEvalResult] = []

    for sample in samples:
        baseline = evaluate_sample(sample, baseline_config)
        if baseline.skipped:
            continue

        dense_chunks = retrieve_chunks(
            sample.query,
            top_k=dense_k,
            search_type=baseline_config.search_type,
            fetch_k=max(baseline_config.fetch_k, dense_k),
            reranker_enabled=baseline_config.reranker_enabled,
        )
        lexical_chunks = _rank_lexical_chunks(sample.query, index_chunks, top_k=lexical_k)
        hybrid_chunks = _rrf_fuse(
            dense_chunks,
            lexical_chunks,
            top_k=baseline_config.top_k,
            rrf_k=rrf_k,
            lexical_weight=lexical_weight,
        )
        hybrid_passed, hybrid_source_hit, hybrid_hit_ranks, hybrid_matched_keywords = _evaluate_hybrid_chunks(
            sample,
            hybrid_chunks,
        )
        results.append(
            HybridEvalResult(
                sample=sample,
                baseline=baseline,
                hybrid_passed=hybrid_passed,
                hybrid_source_hit=hybrid_source_hit,
                hybrid_hit_ranks=hybrid_hit_ranks,
                hybrid_matched_keywords=hybrid_matched_keywords,
                hybrid_chunks=hybrid_chunks,
                dense_sources=[chunk.source for chunk in dense_chunks],
                lexical_sources=[chunk.source for chunk in lexical_chunks],
            )
        )

    return results


def _summarize(results: list[HybridEvalResult]) -> dict[str, int | float]:
    total = len(results)
    baseline_passed = sum(1 for result in results if result.baseline.passed)
    hybrid_passed = sum(1 for result in results if result.hybrid_passed)
    improved = sum(1 for result in results if not result.baseline.passed and result.hybrid_passed)
    regressed = sum(1 for result in results if result.baseline.passed and not result.hybrid_passed)
    return {
        "scored": total,
        "baseline_passed": baseline_passed,
        "baseline_pass_rate": round(baseline_passed / total, 4) if total else 0.0,
        "hybrid_passed": hybrid_passed,
        "hybrid_pass_rate": round(hybrid_passed / total, 4) if total else 0.0,
        "improved": improved,
        "regressed": regressed,
    }


def _result_to_dict(result: HybridEvalResult) -> dict[str, Any]:
    return {
        "id": result.sample.id,
        "query": result.sample.query,
        "expected_sources": result.sample.expected_sources,
        "baseline_passed": result.baseline.passed,
        "baseline_sources": [chunk.source for chunk in result.baseline.chunks],
        "hybrid_passed": result.hybrid_passed,
        "hybrid_sources": [chunk.source for chunk in result.hybrid_chunks],
        "hybrid_matched_keywords": result.hybrid_matched_keywords,
        "dense_sources": result.dense_sources,
        "lexical_sources": result.lexical_sources,
    }


def _write_report(path: str | Path, summary: dict[str, Any], results: list[HybridEvalResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "changed_results": [
            _result_to_dict(result)
            for result in results
            if result.baseline.passed != result.hybrid_passed
        ],
        "hybrid_failures": [_result_to_dict(result) for result in results if not result.hybrid_passed],
    }
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate an offline dense + lexical hybrid retrieval prototype.")
    parser.add_argument("--dataset", default=str(DEFAULT_RETRIEVAL_EVAL_PATH), help="Path to retrieval eval jsonl.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to JSON diagnostic report.")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples.")
    parser.add_argument("--search-type", default="similarity", choices=["similarity", "mmr"], help="Dense baseline type.")
    parser.add_argument("--top-k", type=int, default=3, help="Final top-k to score.")
    parser.add_argument("--fetch-k", type=int, default=8, help="Fetch-k for dense baseline.")
    parser.add_argument("--dense-k", type=int, default=8, help="Dense candidate count before fusion.")
    parser.add_argument("--lexical-k", type=int, default=8, help="Lexical candidate count before fusion.")
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF smoothing constant.")
    parser.add_argument("--lexical-weight", type=float, default=1.0, help="Weight for lexical RRF scores.")
    parser.add_argument("--reranker", default="on", choices=["off", "on"], help="Dense baseline reranker mode.")
    parser.add_argument("--show-changes", action="store_true", help="Print samples improved or regressed by hybrid.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()
    samples = load_retrieval_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    baseline_config = RetrievalEvalConfig(
        search_type=args.search_type,
        top_k=args.top_k,
        fetch_k=max(args.fetch_k, args.top_k),
        reranker_enabled=args.reranker == "on",
    )
    results = evaluate_hybrid_search(
        samples,
        baseline_config=baseline_config,
        dense_k=max(args.dense_k, args.top_k),
        lexical_k=max(args.lexical_k, args.top_k),
        rrf_k=args.rrf_k,
        lexical_weight=args.lexical_weight,
    )
    summary = _summarize(results)
    _write_report(args.output, summary, results)

    print(
        "summary scored={scored} baseline_passed={baseline_passed} baseline_pass_rate={baseline_pass_rate:.2%} "
        "hybrid_passed={hybrid_passed} hybrid_pass_rate={hybrid_pass_rate:.2%} "
        "improved={improved} regressed={regressed}".format(**summary)
    )
    print(f"report_written={Path(args.output).as_posix()}")

    if args.show_changes:
        for result in results:
            if result.baseline.passed == result.hybrid_passed:
                continue
            status = "IMPROVED" if result.hybrid_passed else "REGRESSED"
            print(f"[{status}] {result.sample.id} | {result.sample.query}")
            print(f"  baseline_sources={[chunk.source for chunk in result.baseline.chunks]}")
            print(f"  hybrid_sources={[chunk.source for chunk in result.hybrid_chunks]}")
            print(f"  lexical_sources={result.lexical_sources}")
            print(f"  hybrid_keywords={result.hybrid_matched_keywords}")


if __name__ == "__main__":
    main()
