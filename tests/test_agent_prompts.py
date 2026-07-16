from app.agent.prompts import BASE_SYSTEM_PROMPT, RAG_POLICY_PROMPT, compose_system_prompt


def test_compose_system_prompt_uses_default_and_agentic_rag_policy() -> None:
    prompt = compose_system_prompt()

    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert prompt.endswith(RAG_POLICY_PROMPT)


def test_custom_system_prompt_keeps_agentic_rag_policy() -> None:
    prompt = compose_system_prompt("Answer like a domain expert.")

    assert prompt.startswith("Answer like a domain expert.")
    assert "Decide whether retrieval is needed" in prompt
    assert "Answer directly when retrieval would add no value" in prompt
    assert "untrusted data" in prompt
