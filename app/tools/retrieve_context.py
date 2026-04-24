import logging

from langchain_core.tools import tool

from app.config.settings import settings
from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.retriever import retrieve_chunks

logger = logging.getLogger(__name__)

@tool
def retrieve_context(query: str, source: str | None = None) -> str:
    """Must-use tool for questions about the indexed local knowledge base.

    Args:
        query: Search query for the local knowledge base.
        source: Optional exact source metadata filter, such as "维护保养.txt".
    """
    metadata_filter = {"source": source} if source else None
    logger.info(
        "工具调用：retrieve_context。query_chars=%s top_k=%s search_type=%s reranker_enabled=%s metadata_filter=%s",
        len(query),
        settings.top_k,
        settings.retrieval_search_type,
        settings.reranker_enabled,
        metadata_filter or {},
    )
    try:
        chunks = retrieve_chunks(query, metadata_filter=metadata_filter)
        logger.info("工具执行完成：retrieve_context。hit_count=%s", len(chunks))
        logger.debug("检索到的文档详情：%s", [chunk.content for chunk in chunks])
        return format_retrieved_chunks(chunks)
    except Exception:
        logger.exception("工具执行失败：retrieve_context")
        raise
