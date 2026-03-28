from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config.settings import settings


def get_embeddings() -> OpenAIEmbeddings:
    kwargs = {
        "model": settings.embedding_model,
        "api_key": settings.openai_api_key,
        "check_embedding_ctx_length": False,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAIEmbeddings(**kwargs)

def  get_vector_store() -> Chroma:
    vector_store = Chroma(
        collection_name=settings.collection_name,
        persist_directory=settings.vector_db_dir,
        embedding_function=get_embeddings()
    )
    return vector_store



# if __name__ == "__main__":
    # test_embeddings()