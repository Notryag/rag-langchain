from __future__ import annotations

import unittest

from app.services.metrics_service import MetricsService


class MetricsServiceTests(unittest.TestCase):
    def test_records_chat_feedback_and_errors(self) -> None:
        service = MetricsService()

        service.record_chat(elapsed_ms=100)
        service.record_chat(elapsed_ms=300, stream=True)
        service.record_chat(elapsed_ms=None, stream=True)
        service.record_chat_error()
        service.record_feedback("up")
        service.record_feedback("down")
        service.record_feedback("down")

        snapshot = service.snapshot()

        self.assertEqual(snapshot.chat_requests_total, 1)
        self.assertEqual(snapshot.chat_stream_requests_total, 2)
        self.assertEqual(snapshot.chat_errors_total, 1)
        self.assertEqual(snapshot.feedback_total, 3)
        self.assertEqual(snapshot.feedback_up_total, 1)
        self.assertEqual(snapshot.feedback_down_total, 2)
        self.assertEqual(snapshot.average_chat_elapsed_ms, 200)
        self.assertEqual(snapshot.last_chat_elapsed_ms, 300)
        self.assertGreaterEqual(snapshot.uptime_seconds, 0)


if __name__ == "__main__":
    unittest.main()
