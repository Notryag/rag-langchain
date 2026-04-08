import logging

from langchain_core.tools import tool

from app.config.settings import settings
from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.retriever import retrieve_chunks

logger = logging.getLogger(__name__)

@tool
def retrieve_context(query: str) -> str:
    """Must-use tool for questions about the indexed local knowledge base. Returns citation-formatted retrieved context."""
    logger.info(
        "工具调用：retrieve_context。query_chars=%s top_k=%s search_type=%s reranker_enabled=%s",
        len(query),
        settings.top_k,
        settings.retrieval_search_type,
        settings.reranker_enabled,
    )
    try:
        chunks = retrieve_chunks(query)
        logger.info("工具执行完成：retrieve_context。hit_count=%s", len(chunks))
        logger.debug("检索到的文档详情：%s", [chunk.content for chunk in chunks])
        return format_retrieved_chunks(chunks)
    except Exception:
        logger.exception("工具执行失败：retrieve_context")
        raise
