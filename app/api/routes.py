from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamAnswerData,
    ChatStreamErrorData,
    ChatStreamToolData,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    PublicConfigResponse,
    ThreadResponse,
)
from app.config.settings import settings
from app.retrieval.citations import Citation
from app.retrieval.formatter import format_citation_label
from app.services.feedback_service import get_feedback_service
from app.services.chat_client import new_thread_id
from app.services.rag_service import get_rag_service
from app.services.rag_types import RagResponse, RagStreamEvent

router = APIRouter(prefix="/api")


def _serialize_citation(citation: Citation) -> dict[str, Any]:
    serialized = dict(citation)
    serialized["label"] = format_citation_label(citation)
    return serialized


def _serialize_response(response: RagResponse) -> ChatResponse:
    return ChatResponse(
        thread_id=response.thread_id,
        answer=response.answer,
        status_lines=response.status_lines,
        citations=[_serialize_citation(citation) for citation in response.citations],
        usage=response.usage,
        elapsed_ms=response.elapsed_ms,
    )


def _sse_payload(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _serialize_stream_event(event: RagStreamEvent) -> tuple[str, dict[str, Any]] | None:
    if event.type == "answer":
        payload = ChatStreamAnswerData(content=event.content, answer=event.answer)
        return "answer", payload.model_dump()

    if event.type in {"tool_call", "tool_result"}:
        payload = ChatStreamToolData(
            status_line=event.status_line,
            tool_name=event.tool_name,
            content=event.content,
            citations=[_serialize_citation(citation) for citation in event.citations],
        )
        return event.type, payload.model_dump()

    if event.type == "complete" and event.result is not None:
        return "complete", _serialize_response(event.result).model_dump()

    return None


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/config", response_model=PublicConfigResponse)
def public_config() -> PublicConfigResponse:
    return PublicConfigResponse(
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
        top_k=settings.top_k,
        retrieval_search_type=settings.retrieval_search_type,
        retrieval_fetch_k=settings.retrieval_fetch_k,
        reranker_enabled=settings.reranker_enabled,
        reranker_strategy=settings.reranker_strategy,
        retrieval_max_context_chars=settings.retrieval_max_context_chars,
        collection_name=settings.collection_name,
    )


@router.post("/threads", response_model=ThreadResponse)
def create_thread() -> ThreadResponse:
    return ThreadResponse(thread_id=new_thread_id("web"))


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        record = get_feedback_service().record(
            thread_id=request.thread_id.strip(),
            message_id=request.message_id.strip(),
            rating=request.rating,
            question=request.question.strip() if request.question else None,
            answer=request.answer.strip() if request.answer else None,
            comment=request.comment.strip() if request.comment else None,
            citations=request.citations,
            metadata=request.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FeedbackResponse(feedback_id=record.feedback_id, status="recorded")


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        response = get_rag_service().ask(
            request.message.strip(),
            thread_id=request.thread_id,
            retrieval_profile=request.retrieval_profile.to_profile() if request.retrieval_profile else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _serialize_response(response)


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_generator():
        try:
            for event in get_rag_service().stream(
                request.message.strip(),
                thread_id=request.thread_id,
                retrieval_profile=request.retrieval_profile.to_profile() if request.retrieval_profile else None,
            ):
                serialized = _serialize_stream_event(event)
                if serialized is None:
                    continue
                event_name, payload = serialized
                yield _sse_payload(event_name, payload)
        except Exception as exc:
            yield _sse_payload("error", ChatStreamErrorData(message=str(exc)).model_dump())

    return StreamingResponse(event_generator(), media_type="text/event-stream")
