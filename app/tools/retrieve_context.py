from textwrap import shorten

from langchain_core.documents import Document
from langchain_core.tools import tool

from app.config.settings import settings
from app.retrieval.vectorstore import get_vector_store


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
    vector_store = get_vector_store()
    docs = vector_store.similarity_search(query, k = settings.top_k)
    return _format_docs(docs)