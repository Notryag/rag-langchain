import logging
from textwrap import shorten

from langchain_core.tools import tool

from app.config.settings import settings
from app.retrieval.vectorstore import get_vector_store

logger = logging.getLogger(__name__)


def _format_docs(docs: list) -> str:
    if not docs:
        return "No relevant context found."

    blocks = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "")
        page_text = f", page={page}" if page != "" else ""
        content = shorten(doc.page_content.replace("\n", " "), width=1200, placeholder="...")
        blocks.append(f"[{i}] source={source}{page_text}\n{content}")

    return "\n\n".join(blocks)

@tool
def retrieve_context(query:str) -> str:
    """Retrieve information to help answer a query."""
    logger.info(
        "工具调用：retrieve_context。query_chars=%s top_k=%s 预览=%s",
        len(query),
        settings.top_k,
        shorten(query.replace("\n", " "), width=120, placeholder="..."),
    )
    try:
        vector_store = get_vector_store()
        docs = vector_store.similarity_search(query, k=settings.top_k)
        logger.info("工具执行完成：retrieve_context。hit_count=%s", len(docs))
        return _format_docs(docs)
    except Exception:
        logger.exception("工具执行失败：retrieve_context")
        raise
