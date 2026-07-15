from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.chat_service import ChatAnswer
from evaluation.evaluate_answers import AnswerRun, _load_runs, _summarize, evaluate_answers
from evaluation.dataset import AnswerEvalSample
from evaluation.generate_pgvector_answers import (
    PgVectorAnswerRunConfig,
    build_answer_run_record,
    generate_pgvector_answer_runs,
)


def _sample(**overrides) -> AnswerEvalSample:
    payload = {
        "id": "ans_1",
        "query": "怎么计费？",
        "category": "billing",
        "expected_facts": ["调用次数", "存储容量"],
        "expected_min_fact_hits": 2,
        "answerable": True,
    }
    payload.update(overrides)
    return AnswerEvalSample.from_dict(payload)


class FakeChatService:
    def __init__(self) -> None:
        self.calls = []

    def ask(self, session, *, user_id, kb_id, question, session_id=None):
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "kb_id": kb_id,
                "question": question,
                "session_id": session_id,
            }
        )
        return ChatAnswer(
            answer="根据资料回答。",
            references=[{"filename": "manual.txt", "chunk_id": 1, "content": "引用"}],
            session_id=10,
            run_id=20,
            cache_hit=False,
            usage={"total_tokens": 12},
        )


class PgVectorAnswerGenerationTests(unittest.TestCase):
    def test_build_answer_run_record_keeps_references_and_run_metadata(self) -> None:
        sample = _sample()
        answer = ChatAnswer(
            answer="根据资料回答。",
            references=[{"filename": "manual.txt"}],
            session_id=10,
            run_id=20,
            cache_hit=True,
            usage={"total_tokens": 12},
        )

        record = build_answer_run_record(
            sample,
            answer,
            config=PgVectorAnswerRunConfig(user_id=1, kb_id=2),
            elapsed_ms=123,
        )

        self.assertEqual(record["backend"], "pgvector")
        self.assertEqual(record["user_id"], 1)
        self.assertEqual(record["kb_id"], 2)
        self.assertEqual(record["session_id"], 10)
        self.assertEqual(record["run_id"], 20)
        self.assertEqual(record["references"][0]["filename"], "manual.txt")
        self.assertTrue(record["cache_hit"])
        self.assertIsNone(record["token_cost"])

    def test_generate_pgvector_answer_runs_calls_chat_service_with_tenant_scope(self) -> None:
        chat_service = FakeChatService()
        session = object()

        records = generate_pgvector_answer_runs(
            [_sample(), _sample(id="ans_2", query="怎么退款？")],
            session=session,
            chat_service=chat_service,
            config=PgVectorAnswerRunConfig(user_id=1, kb_id=2),
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(chat_service.calls[0]["session"], session)
        self.assertEqual(chat_service.calls[0]["user_id"], 1)
        self.assertEqual(chat_service.calls[0]["kb_id"], 2)
        self.assertEqual(chat_service.calls[0]["question"], "怎么计费？")
        self.assertEqual(records[0]["answer"], "根据资料回答。")

    def test_answer_eval_loader_keeps_pgvector_run_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "runs.jsonl"
            path.write_text(
                (
                    '{"id":"ans_1","query":"怎么计费？","category":"billing",'
                    '"answer":"回答","elapsed_ms":12,"usage":{"total_tokens":3},'
                    '"backend":"pgvector","run_id":20,"references":[{"filename":"manual.txt"}]}'
                    "\n"
                ),
                encoding="utf-8",
            )

            runs = _load_runs(path)

        self.assertEqual(runs["ans_1"].metadata["backend"], "pgvector")
        self.assertEqual(runs["ans_1"].metadata["run_id"], 20)
        self.assertEqual(runs["ans_1"].metadata["references"][0]["filename"], "manual.txt")

    def test_answer_summary_records_citation_latency_and_cost(self) -> None:
        sample = _sample(expected_sources=["manual.txt"])
        run = {
            "ans_1": AnswerRun(
                id="ans_1", query=sample.query, category=sample.category, answer="调用次数和存储容量",
                elapsed_ms=12, usage={"total_tokens": 5},
                metadata={"references": [{"filename": "manual.txt"}], "token_cost": {"total_cost": 0.01}},
            )
        }
        result = evaluate_answers([sample], run)
        summary = _summarize(result)
        self.assertEqual(summary["citation_accuracy"], 1.0)
        self.assertEqual(summary["p95_elapsed_ms"], 12.0)
        self.assertEqual(summary["total_cost_usd"], 0.01)


if __name__ == "__main__":
    unittest.main()
