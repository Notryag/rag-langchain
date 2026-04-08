from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import product
from pathlib import Path

from app.config.logging_setup import setup_logging
from app.retrieval.retriever import RetrievedChunk, retrieve_chunks
from evaluation.dataset import DEFAULT_RETRIEVAL_EVAL_PATH, RetrievalEvalSample, load_retrieval_eval_samples


@dataclass(frozen=True)
class RetrievalEvalConfig:
    search_type: str
    top_k: int
    fetch_k: int

    @property
    def label(self) -> str:
        return f"search_type={self.search_type} top_k={self.top_k} fetch_k={self.fetch_k}"


@dataclass(frozen=True)
class RetrievalEvalResult:
    sample: RetrievalEvalSample
    config: RetrievalEvalConfig
    skipped: bool
    passed: bool
    source_hit: bool
    hit_ranks: list[int]
    matched_keywords: list[str]
    required_keyword_hits: int
    chunks: list[RetrievedChunk]


def _build_configs(search_types: list[str], top_ks: list[int], fetch_ks: list[int]) -> list[RetrievalEvalConfig]:
    return [
        RetrievalEvalConfig(
            search_type=search_type,
            top_k=top_k,
            fetch_k=max(fetch_k, top_k),
        )
        for search_type, top_k, fetch_k in product(search_types, top_ks, fetch_ks)
    ]


def _match_keywords(sample: RetrievalEvalSample, chunks: list[RetrievedChunk]) -> list[str]:
    corpus = "\n".join(chunk.content.lower() for chunk in chunks)
    return [keyword for keyword in sample.expected_keywords if keyword.lower() in corpus]


def evaluate_sample(sample: RetrievalEvalSample, config: RetrievalEvalConfig) -> RetrievalEvalResult:
    chunks = retrieve_chunks(
        sample.query,
        top_k=config.top_k,
        search_type=config.search_type,
        fetch_k=config.fetch_k,
    )
    if not sample.score_retrieval:
        return RetrievalEvalResult(
            sample=sample,
            config=config,
            skipped=True,
            passed=False,
            source_hit=False,
            hit_ranks=[],
            matched_keywords=[],
            required_keyword_hits=sample.expected_min_keyword_hits,
            chunks=chunks,
        )

    hit_ranks = [chunk.rank for chunk in chunks if chunk.source in sample.expected_sources]
    matched_keywords = _match_keywords(sample, chunks)
    source_hit = bool(hit_ranks)
    passed = source_hit and len(matched_keywords) >= sample.expected_min_keyword_hits
    return RetrievalEvalResult(
        sample=sample,
        config=config,
        skipped=False,
        passed=passed,
        source_hit=source_hit,
        hit_ranks=hit_ranks,
        matched_keywords=matched_keywords,
        required_keyword_hits=sample.expected_min_keyword_hits,
        chunks=chunks,
    )


def _summarize(results: list[RetrievalEvalResult]) -> dict[str, float | int]:
    scored_results = [result for result in results if not result.skipped]
    source_hits = [result for result in scored_results if result.source_hit]
    passed_results = [result for result in scored_results if result.passed]
    return {
        "total": len(results),
        "scored": len(scored_results),
        "skipped": len(results) - len(scored_results),
        "source_hit": len(source_hits),
        "passed": len(passed_results),
        "source_hit_rate": round(len(source_hits) / len(scored_results), 4) if scored_results else 0.0,
        "pass_rate": round(len(passed_results) / len(scored_results), 4) if scored_results else 0.0,
    }


def _print_result(result: RetrievalEvalResult) -> None:
    retrieved_sources = [chunk.source for chunk in result.chunks]
    if result.skipped:
        status = "SKIP"
    elif result.passed:
        status = "PASS"
    else:
        status = "FAIL"

    print(f"[{status}] {result.sample.id} | {result.sample.query}")
    print(f"  category={result.sample.category}")
    print(f"  expected_sources={result.sample.expected_sources or ['<none>']}")
    print(f"  retrieved_sources={retrieved_sources}")
    if not result.skipped:
        print(
            "  source_hit=%s hit_ranks=%s keywords=%s/%s matched=%s"
            % (
                result.source_hit,
                result.hit_ranks,
                len(result.matched_keywords),
                result.required_keyword_hits,
                result.matched_keywords,
            )
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation against the local vector store.")
    parser.add_argument("--dataset", default=str(DEFAULT_RETRIEVAL_EVAL_PATH), help="Path to retrieval eval jsonl.")
    parser.add_argument("--search-type", nargs="+", default=["similarity"], help="Search types to compare.")
    parser.add_argument("--top-k", nargs="+", type=int, default=[3], help="Top-k values to compare.")
    parser.add_argument("--fetch-k", nargs="+", type=int, default=[8], help="Fetch-k values to compare.")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples.")
    parser.add_argument("--show-passes", action="store_true", help="Print passing samples as well.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()

    samples = load_retrieval_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    configs = _build_configs(args.search_type, args.top_k, args.fetch_k)
    for config in configs:
        print(f"\n=== Retrieval Eval | {config.label} ===")
        results = [evaluate_sample(sample, config) for sample in samples]
        summary = _summarize(results)
        print(
            "summary total={total} scored={scored} skipped={skipped} "
            "source_hit={source_hit} source_hit_rate={source_hit_rate:.2%} "
            "passed={passed} pass_rate={pass_rate:.2%}".format(**summary)
        )

        for result in results:
            if result.passed and not args.show_passes:
                continue
            _print_result(result)


if __name__ == "__main__":
    main()
