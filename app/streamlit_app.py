from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.config.logging_setup import setup_logging
from app.config.settings import settings
from app.retrieval.formatter import format_citation_label
from app.services.rag_service import get_rag_service, new_thread_id

APP_TITLE = "LangChain RAG 控制台"
APP_SUBTITLE = "面向本地知识库的问答界面"


def _ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = new_thread_id("streamlit")


def _reset_chat() -> None:
    st.session_state.messages = []
    st.session_state.thread_id = new_thread_id("streamlit")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --page-bg: linear-gradient(180deg, #f2efe8 0%, #fbf8f2 100%);
            --panel-bg: rgba(255, 252, 246, 0.86);
            --panel-border: rgba(48, 63, 54, 0.10);
            --accent: #244b3c;
            --accent-soft: #dbe8df;
            --text-main: #1f2a24;
            --text-muted: #5f6c65;
        }

        .stApp {
            background: var(--page-bg);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 900px;
        }

        .hero {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 24px;
            padding: 1.4rem 1.5rem;
            box-shadow: 0 18px 48px rgba(36, 75, 60, 0.08);
            margin-bottom: 1.2rem;
        }

        .hero h1 {
            color: var(--text-main);
            font-size: 2rem;
            margin: 0;
        }

        .hero p {
            color: var(--text-muted);
            margin: 0.4rem 0 0;
        }

        [data-testid="stSidebar"] {
            background: rgba(36, 75, 60, 0.96);
        }

        [data-testid="stSidebar"] * {
            color: #f6f3ec;
        }

        .meta-card {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            margin-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(log_path: Path) -> None:
    with st.sidebar:
        st.markdown("### 会话控制")
        st.button("新建会话", on_click=_reset_chat, use_container_width=True)
        st.markdown(
            f"""
            <div class="meta-card">
                <div><strong>模型</strong>: {settings.chat_model}</div>
                <div><strong>Embedding</strong>: {settings.embedding_model}</div>
                <div><strong>Top K</strong>: {settings.top_k}</div>
                <div><strong>检索</strong>: {settings.retrieval_search_type}</div>
                <div><strong>Reranker</strong>: {"on" if settings.reranker_enabled else "off"}</div>
                <div><strong>Context</strong>: {settings.retrieval_max_context_chars} chars</div>
                <div><strong>线程</strong>: {st.session_state.thread_id}</div>
            </div>
            <div class="meta-card">
                <div><strong>向量库</strong>: {settings.vector_db_dir}</div>
                <div><strong>Chunk</strong>: {settings.chunk_size}/{settings.chunk_overlap}</div>
                <div><strong>日志</strong>: {log_path.as_posix()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_assistant_meta(message: dict) -> None:
    status_lines = message.get("status_lines") or []
    if status_lines:
        st.caption(" | ".join(status_lines))

    citations = message.get("citations") or []
    if citations:
        st.caption("引用: " + " | ".join(format_citation_label(citation) for citation in citations))

    meta = message.get("meta") or {}
    usage = meta.get("usage") or {}
    elapsed_ms = meta.get("elapsed_ms")
    parts = []
    if elapsed_ms is not None:
        parts.append(f"{elapsed_ms} ms")
    total_tokens = usage.get("total_tokens")
    if total_tokens is not None:
        parts.append(f"tokens={total_tokens}")
    parts.append(f"search={settings.retrieval_search_type}")
    parts.append(f"reranker={'on' if settings.reranker_enabled else 'off'}")
    if parts:
        st.caption(" | ".join(parts))


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📚",
        layout="centered",
    )
    log_path = setup_logging()
    rag_service = get_rag_service()
    _ensure_session_state()
    _inject_styles()
    _render_sidebar(log_path)

    st.markdown(
        f"""
        <section class="hero">
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUBTITLE}，基于当前 Chroma 向量库和 LangChain Agent。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                _render_assistant_meta(message)
            st.markdown(message["content"])

    prompt = st.chat_input("输入问题，回车发送")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        answer_placeholder = st.empty()
        answer = ""
        status_lines: list[str] = []
        citations: list[dict] = []
        meta: dict = {}
        final_result = None

        try:
            for event in rag_service.stream(prompt, thread_id=st.session_state.thread_id):
                if event.type == "tool_call":
                    status_lines.append(event.status_line)
                    status_placeholder.caption(" | ".join(status_lines))
                    continue

                if event.type == "tool_result":
                    status_lines.append(event.status_line)
                    for citation in event.citations:
                        if citation not in citations:
                            citations.append(citation)
                    status_placeholder.caption(" | ".join(status_lines))
                    continue

                if event.type == "answer":
                    answer = event.answer
                    answer_placeholder.markdown(answer)
                    continue

                if event.type == "complete":
                    final_result = event.result
                    if final_result is not None:
                        answer = final_result.answer
                        citations = final_result.citations
                        meta = {
                            "usage": final_result.usage,
                            "elapsed_ms": final_result.elapsed_ms,
                        }
        except Exception as exc:
            answer = f"请求失败：{exc}"
            answer_placeholder.markdown(answer)

        _render_assistant_meta(
            {
                "status_lines": final_result.status_lines if final_result else status_lines,
                "meta": meta,
                "citations": final_result.citations if final_result else citations,
            }
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "status_lines": final_result.status_lines if final_result else status_lines,
            "citations": final_result.citations if final_result else citations,
            "meta": meta,
        }
    )


if __name__ == "__main__":
    main()
