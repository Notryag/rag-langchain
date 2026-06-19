import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    kwargs = {
        "model": settings.embedding_model,
        "api_key": settings.openai_api_key,
        "check_embedding_ctx_length": False,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    logger.info(
        "初始化 Embeddings。model=%s 已配置_base_url=%s",
        settings.embedding_model,
        bool(settings.openai_base_url),
    )
    return OpenAIEmbeddings(**kwargs)
