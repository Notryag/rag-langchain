from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, MessagesState, StateGraph

from app.config.settings import Settings
from app.memory.checkpointer import build_checkpointer


def _settings_for_checkpointer(checkpointer_type: str, sqlite_path: str = "") -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_base_url=None,
        chat_model="test-chat",
        embedding_model="test-embedding",
        vector_db_dir="./storage/chroma",
        collection_name="rag_docs",
        top_k=3,
        retrieval_search_type="similarity",
        retrieval_fetch_k=8,
        reranker_enabled=False,
        reranker_strategy="embedding_lexical",
        retrieval_max_context_chars=4000,
        chunk_size=800,
        chunk_overlap=120,
        log_dir="./logs",
        log_level="INFO",
        log_file_name="app.log",
        checkpointer_type=checkpointer_type,
        checkpointer_sqlite_path=sqlite_path,
        feedback_log_path="./storage/feedback.jsonl",
    )


class CheckpointerTests(unittest.TestCase):
    def test_memory_checkpointer(self) -> None:
        checkpointer = build_checkpointer(_settings_for_checkpointer("memory"))

        self.assertIsInstance(checkpointer, InMemorySaver)

    def test_sqlite_checkpointer_initializes_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "nested" / "checkpoints.sqlite3"
            checkpointer = build_checkpointer(_settings_for_checkpointer("sqlite", str(db_path)))
            self.assertIsInstance(checkpointer, SqliteSaver)
            checkpointer.conn.close()

            self.assertTrue(db_path.exists())
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            try:
                table_names = {row[0] for row in cursor.fetchall()}
            finally:
                cursor.close()
                conn.close()

            self.assertIn("checkpoints", table_names)
            self.assertIn("writes", table_names)

    def test_sqlite_checkpointer_restores_thread_state(self) -> None:
        def echo_message_count(state: MessagesState) -> dict[str, list[AIMessage]]:
            return {"messages": [AIMessage(content=f"seen {len(state['messages'])}")]}

        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("echo", echo_message_count)
        graph_builder.add_edge(START, "echo")

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "checkpoints.sqlite3"
            config = _settings_for_checkpointer("sqlite", str(db_path))
            thread_config = {"configurable": {"thread_id": "test-thread"}}

            first_checkpointer = build_checkpointer(config)
            first_graph = graph_builder.compile(checkpointer=first_checkpointer)
            first_result = first_graph.invoke(
                {"messages": [HumanMessage(content="first")]},
                config=thread_config,
            )
            first_checkpointer.conn.close()

            second_checkpointer = build_checkpointer(config)
            second_graph = graph_builder.compile(checkpointer=second_checkpointer)
            second_result = second_graph.invoke(
                {"messages": [HumanMessage(content="second")]},
                config=thread_config,
            )
            second_checkpointer.conn.close()

            self.assertEqual([message.content for message in first_result["messages"]], ["first", "seen 1"])
            self.assertEqual(
                [message.content for message in second_result["messages"]],
                ["first", "seen 1", "second", "seen 3"],
            )

    def test_rejects_empty_sqlite_path(self) -> None:
        with self.assertRaises(ValueError):
            _settings_for_checkpointer("sqlite", "")


if __name__ == "__main__":
    unittest.main()
