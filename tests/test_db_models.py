from __future__ import annotations

import unittest

from pgvector.sqlalchemy import Vector

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models.chat import ChatRole, ChatRunStatus
from app.db.models.document import DocumentStatus
from app.db.models.user import UserRole


class DbModelTests(unittest.TestCase):
    def test_core_tables_are_registered(self) -> None:
        self.assertEqual(
            {
                "users",
                "knowledge_bases",
                "documents",
                "document_chunks",
                "chat_sessions",
                "chat_messages",
                "chat_runs",
                "chat_run_events",
                "prompt_versions",
                "operation_logs",
            },
            set(Base.metadata.tables),
        )

    def test_operation_logs_keep_actor_resource_and_details(self) -> None:
        table = Base.metadata.tables["operation_logs"]

        self.assertIn("user_id", table.columns)
        self.assertIn("action", table.columns)
        self.assertIn("resource_type", table.columns)
        self.assertIn("resource_id", table.columns)
        self.assertIn("details", table.columns)

        index_names = {index.name for index in table.indexes}
        self.assertIn("ix_operation_logs_user_created", index_names)
        self.assertIn("ix_operation_logs_resource", index_names)

    def test_document_status_values(self) -> None:
        self.assertEqual(
            [status.value for status in DocumentStatus],
            ["pending", "processing", "completed", "failed"],
        )

    def test_chat_role_values(self) -> None:
        self.assertEqual([role.value for role in ChatRole], ["user", "assistant", "system"])

    def test_user_role_values_and_prompt_constraints(self) -> None:
        self.assertEqual([role.value for role in UserRole], ["user", "admin"])
        self.assertIn("role", Base.metadata.tables["users"].columns)
        prompt_indexes = {index.name for index in Base.metadata.tables["prompt_versions"].indexes}
        self.assertIn("uq_prompt_versions_name_version", prompt_indexes)
        self.assertIn("uq_prompt_versions_single_active", prompt_indexes)

    def test_chat_run_status_values(self) -> None:
        self.assertEqual(
            [status.value for status in ChatRunStatus],
            ["running", "completed", "failed", "cancelled"],
        )

    def test_chat_runs_keep_lifecycle_fields(self) -> None:
        table = Base.metadata.tables["chat_runs"]

        self.assertIn("session_id", table.columns)
        self.assertIn("user_id", table.columns)
        self.assertIn("kb_id", table.columns)
        self.assertIn("prompt_version_id", table.columns)
        self.assertIn("status", table.columns)
        self.assertIn("question", table.columns)
        self.assertIn("answer", table.columns)
        self.assertIn("references", table.columns)
        self.assertIn("usage", table.columns)
        self.assertIn("token_cost", table.columns)
        self.assertIn("trace_id", table.columns)
        self.assertIn("trace_url", table.columns)
        self.assertIn("cache_hit", table.columns)
        self.assertIn("error_message", table.columns)

        index_names = {index.name for index in table.indexes}
        self.assertIn("ix_chat_runs_user_kb_status", index_names)
        self.assertIn("ix_chat_runs_session_created", index_names)

    def test_chat_run_events_keep_timeline_fields(self) -> None:
        table = Base.metadata.tables["chat_run_events"]

        self.assertIn("run_id", table.columns)
        self.assertIn("user_id", table.columns)
        self.assertIn("kb_id", table.columns)
        self.assertIn("event_type", table.columns)
        self.assertIn("sequence", table.columns)
        self.assertIn("payload", table.columns)

        index_names = {index.name for index in table.indexes}
        self.assertIn("ix_chat_run_events_run_sequence", index_names)
        self.assertIn("ix_chat_run_events_user_kb_created", index_names)

    def test_chunk_keeps_tenant_scope_and_vector_embedding(self) -> None:
        table = Base.metadata.tables["document_chunks"]

        self.assertIn("user_id", table.columns)
        self.assertIn("kb_id", table.columns)
        self.assertIn("document_id", table.columns)
        self.assertIn("metadata", table.columns)
        self.assertIsInstance(table.columns["embedding"].type, Vector)

        index_names = {index.name for index in table.indexes}
        self.assertIn("ix_document_chunks_tenant_scope", index_names)
        self.assertIn("ix_document_chunks_embedding", index_names)


if __name__ == "__main__":
    unittest.main()
