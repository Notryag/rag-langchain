from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.workers.tasks import enqueue_document_processing, process_document_task


class WorkerTaskTests(unittest.TestCase):
    def test_processing_task_has_reliability_limits(self) -> None:
        self.assertTrue(process_document_task.acks_late)
        self.assertTrue(process_document_task.reject_on_worker_lost)
        self.assertEqual(process_document_task.max_retries, 3)
        self.assertEqual(process_document_task.soft_time_limit, 300)
        self.assertEqual(process_document_task.time_limit, 330)

    def test_enqueue_document_processing_returns_task_id(self) -> None:
        with patch("app.workers.tasks.process_document_task.delay", return_value=SimpleNamespace(id="task-1")) as delay:
            task_id = enqueue_document_processing(12)

        self.assertEqual(task_id, "task-1")
        delay.assert_called_once_with(12)


if __name__ == "__main__":
    unittest.main()
