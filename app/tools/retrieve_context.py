import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.profile import RetrievalProfile
from app.retrieval.retriever import retrieve_chunks

logger = logging.getLogger(__name__)


def _profile_from_runtime(runtime: ToolRuntime | None) -> RetrievalProfile:
    if runtime is None:
        return RetrievalProfile.from_settings()

    payload = (runtime.context or {}).get("retrieval_profile")
    if isinstance(payload, dict):
        return RetrievalProfile.from_mapping(payload)
    return RetrievalProfile.from_settings()


@tool
def retrieve_context(query: str, runtime: ToolRuntime, source: str | None = None) -> str:
    """Must-use tool for questions about the indexed local knowledge base.

    Args:
        query: Search query for the local knowledge base.
        source: Optional exact source metadata filter, such as "维护保养.txt".
    """
    profile = _profile_from_runtime(runtime)
    metadata_filter = {"source": source} if source else None
    logger.info(
        "工具调用：retrieve_context。query_chars=%s top_k=%s search_type=%s reranker_enabled=%s metadata_filter=%s",
        len(query),
        profile.top_k,
        profile.search_type,
        profile.reranker_enabled,
        metadata_filter or {},
    )
    try:
        chunks = retrieve_chunks(query, profile=profile, metadata_filter=metadata_filter)
        logger.info("工具执行完成：retrieve_context。hit_count=%s", len(chunks))
        logger.debug("检索到的文档详情：%s", [chunk.content for chunk in chunks])
        return format_retrieved_chunks(chunks, max_context_chars=profile.max_context_chars)
    except Exception:
        logger.exception("工具执行失败：retrieve_context")
        raise
