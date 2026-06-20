from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompts import BASE_SYSTEM_PROMPT
from app.db.models.prompt import PromptVersion


DEFAULT_PROMPT_NAME = "default_rag_assistant"
DEFAULT_PROMPT_VERSION = "v1"


class PromptVersionService:
    def get_active(self, session: Session) -> PromptVersion:
        statement = (
            select(PromptVersion)
            .where(PromptVersion.is_active.is_(True))
            .order_by(PromptVersion.created_at.desc(), PromptVersion.id.desc())
        )
        active = session.scalar(statement)
        if active is not None:
            return active
        return self.ensure_default(session)

    def ensure_default(self, session: Session) -> PromptVersion:
        statement = select(PromptVersion).where(
            PromptVersion.name == DEFAULT_PROMPT_NAME,
            PromptVersion.version == DEFAULT_PROMPT_VERSION,
        )
        existing = session.scalar(statement)
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
                session.commit()
                session.refresh(existing)
            return existing

        prompt_version = PromptVersion(
            name=DEFAULT_PROMPT_NAME,
            version=DEFAULT_PROMPT_VERSION,
            description="Default RAG assistant prompt used by the built-in Agent.",
            system_prompt=BASE_SYSTEM_PROMPT,
            is_active=True,
        )
        session.add(prompt_version)
        session.commit()
        session.refresh(prompt_version)
        return prompt_version


def get_prompt_version_service() -> PromptVersionService:
    return PromptVersionService()
