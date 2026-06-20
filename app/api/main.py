from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_error_handlers
from app.api.rate_limit import enforce_rate_limit
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as document_router
from app.api.v1.knowledge_bases import router as knowledge_base_router
from app.api.v1.prompts import router as prompt_router
from app.api.v1.system import router as system_router
from app.config.logging_setup import setup_logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="LangChain RAG API", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(auth_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(knowledge_base_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(document_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(chat_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(prompt_router, dependencies=[Depends(enforce_rate_limit)])


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
