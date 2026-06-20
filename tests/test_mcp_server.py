from __future__ import annotations

import unittest
from unittest.mock import patch

from app.mcp.server import kb_search, mcp


class _FakeRetrievedChunk:
    def to_reference(self) -> dict[str, object]:
        return {
            "document_id": 7,
            "filename": "manual.txt",
            "chunk_id": 11,
            "chunk_index": 2,
            "content": "quoted content",
        }


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_registers_expected_tools(self) -> None:
        tools = await mcp.list_tools()

        self.assertEqual(
            {tool.name for tool in tools},
            {"kb_search", "document_lookup", "get_chat_run"},
        )

    @patch("app.mcp.server.retrieve_pgvector_retrieved_chunks")
    @patch("app.mcp.server.get_session_factory")
    def test_kb_search_preserves_tenant_scope(self, get_session_factory, retrieve_chunks) -> None:
        get_session_factory.return_value.return_value = _FakeSession()
        retrieve_chunks.return_value = [_FakeRetrievedChunk()]

        references = kb_search(user_id=3, kb_id=5, query="refund policy", top_k=4, search_type="hybrid")

        self.assertEqual(references[0]["document_id"], 7)
        _, kwargs = retrieve_chunks.call_args
        self.assertEqual(kwargs["user_id"], 3)
        self.assertEqual(kwargs["kb_id"], 5)
        self.assertEqual(kwargs["query"], "refund policy")
        self.assertEqual(kwargs["top_k"], 4)
        self.assertEqual(kwargs["search_type"], "hybrid")


if __name__ == "__main__":
    unittest.main()
