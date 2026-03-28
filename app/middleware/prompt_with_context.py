
from langchain.agents.middleware import ModelRequest, dynamic_prompt


@dynamic_prompt
def prompt_with_context(request: ModelRequest) -> str:
    return (
        "You are a helpful RAG assistant.\n"
        "Rules:\n"
        "1. For questions about the indexed knowledge base, prefer using the retrieve_context tool.\n"
        "2. If retrieved context exists, answer strictly based on it.\n"
        "3. If the context is insufficient, say you are not sure instead of making things up.\n"
        "4. Keep answers clear and concise.\n"
        "5. When using retrieved content, mention the source if available.\n"
    )