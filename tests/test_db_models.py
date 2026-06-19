from __future__ import annotations

import unittest

from pgvector.sqlalchemy import Vector

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models.chat import ChatRole
from app.db.models.document import DocumentStatus


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
