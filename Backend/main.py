"""FastAPI entrypoint: indexes corpus on startup and exposes chat + feedback APIs."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.mongo import mongo
from app.llm.openai_client import any_llm_configured, get_active_provider
from app.db.repositories import ChatRepository, FeedbackRepository


def _build_orchestrator():
    from app.agent.orchestrator import Orchestrator
    from app.retrieval.bm25 import BM25Index
    from app.retrieval.indexer import ensure_index_built

    records, chroma = ensure_index_built()
    records_by_id = {r.doc_id: r for r in records}
    bm25_docs = [(r.doc_id, f"{r.title}\n{r.text}") for r in records]
    bm25 = BM25Index(bm25_docs)
    chat_repo = ChatRepository(mongo.db)
    fb_repo = FeedbackRepository(mongo.db)
    return Orchestrator(
        records_by_id=records_by_id,
        bm25=bm25,
        chroma=chroma,
        chats=chat_repo,
        feedback=fb_repo,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    mongo.connect()
    orch = _build_orchestrator()
    app.state.orchestrator = orch
    app.state.chat_repo = orch.chats
    app.state.feedback_repo = orch.feedback
    yield
    mongo.close()


app = FastAPI(title="IR + LLM Research Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_documents import router as documents_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(feedback_router)
app.include_router(documents_router)


@app.get("/config")
def public_config():
    """Non-secret flags for UI."""
    provider = get_active_provider()
    return {
        "openai_configured": any_llm_configured(),
        "llm_provider": provider,
        "debug_trace": settings.debug_trace,
        "model": settings.openai_model if provider == "openai"
                 else settings.gemini_model if provider == "gemini"
                 else settings.groq_model if provider == "groq"
                 else "none",
    }
