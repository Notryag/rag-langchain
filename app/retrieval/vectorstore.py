import logging

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config.settings import settings

logger = logging.getLogger(__name__)


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

def  get_vector_store() -> Chroma:
    logger.info(
        "打开向量库。collection=%s persist_directory=%s",
        settings.collection_name,
        settings.vector_db_dir,
    )
    vector_store = Chroma(
        collection_name=settings.collection_name,
        persist_directory=settings.vector_db_dir,
        embedding_function=get_embeddings()
    )
    return vector_store



# if __name__ == "__main__":
    # test_embeddings()
