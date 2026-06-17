from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.feedback_service import FeedbackService


class FeedbackServiceTests(unittest.TestCase):
    def test_record_appends_jsonl_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "nested" / "feedback.jsonl"
            service = FeedbackService(str(log_path))

            record = service.record(
                thread_id="web_thread",
                message_id="message_1",
                rating="down",
                question="问题",
                answer="回答",
                comment="引用不准确",
                citations=[{"source": "source.txt"}],
                metadata={"search_type": "hybrid"},
            )

            self.assertTrue(log_path.exists())
            payload = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["feedback_id"], record.feedback_id)
            self.assertEqual(payload["thread_id"], "web_thread")
            self.assertEqual(payload["message_id"], "message_1")
            self.assertEqual(payload["rating"], "down")
            self.assertEqual(payload["comment"], "引用不准确")
            self.assertEqual(payload["citations"], [{"source": "source.txt"}])
            self.assertEqual(payload["metadata"], {"search_type": "hybrid"})


if __name__ == "__main__":
    unittest.main()
