
from langchain.agents.middleware import ModelRequest, dynamic_prompt


@dynamic_prompt
def prompt_with_context(request: ModelRequest) -> str:
    return (
        "You are a helpful RAG assistant.\n"
        "Rules:\n"
        "1. For questions about the indexed knowledge base, you must call the retrieve_context tool before answering.\n"
        "2. Do not answer from prior knowledge when retrieve_context has not been called in the current turn.\n"
        "3. If retrieved context exists, answer strictly based on it.\n"
        "4. If the context is insufficient, say you are not sure instead of making things up.\n"
        "5. Keep answers clear and concise.\n"
        "6. When using retrieved content, mention the source if available.\n"
    )
