from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import ChatRequest, ChatResponse, HealthResponse, PublicConfigResponse, ThreadResponse
from app.config.logging_setup import setup_logging
from app.config.settings import settings
from app.retrieval.citations import Citation
from app.retrieval.formatter import format_citation_label
from app.services.chat_client import new_thread_id
from app.services.rag_service import RagResponse, get_rag_service

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="LangChain RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/config", response_model=PublicConfigResponse)
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


@app.post("/api/threads", response_model=ThreadResponse)
def create_thread() -> ThreadResponse:
    return ThreadResponse(thread_id=new_thread_id("web"))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        response = get_rag_service().ask(
            request.message.strip(),
            thread_id=request.thread_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _serialize_response(response)


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_generator():
        try:
            for event in get_rag_service().stream(
                request.message.strip(),
                thread_id=request.thread_id,
            ):
                if event.type == "answer":
                    yield _sse_payload(
                        "answer",
                        {
                            "content": event.content,
                            "answer": event.answer,
                        },
                    )
                    continue

                if event.type in {"tool_call", "tool_result"}:
                    yield _sse_payload(
                        event.type,
                        {
                            "status_line": event.status_line,
                            "tool_name": event.tool_name,
                            "content": event.content,
                            "citations": [_serialize_citation(citation) for citation in event.citations],
                        },
                    )
                    continue

                if event.type == "complete" and event.result is not None:
                    yield _sse_payload("complete", _serialize_response(event.result).model_dump())
        except Exception as exc:
            yield _sse_payload("error", {"message": str(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
