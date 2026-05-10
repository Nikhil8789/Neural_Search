"""End-to-end agent orchestration: understanding → policy → retrieval → explain → RAG."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from langchain_community.vectorstores import Chroma

from app.agent.intent_helpers import wants_multidoc_summary
from app.agent.policy import decide_agent_action
from app.core.config import settings
from app.db.repositories import ChatRepository, FeedbackRepository
from app.explain.explanations import format_sources_for_response
from app.explain.matcher import rank_and_explain
from app.llm.openai_client import (
    any_llm_configured,
    downgrade_provider,
    get_active_provider,
)
from app.llm.query_nlp import heuristic_understanding, llm_query_reformulation, llm_query_understanding
from app.rag.generator import generate_clarification, generate_direct_answer, generate_rag_answer
from app.retrieval.bm25 import BM25Index
from app.retrieval.corpus_loader import DocRecord
from app.retrieval.hybrid import hybrid_retrieve


# ── Error helpers ────────────────────────────────────────────────────────────

def _is_quota_error(exc: Exception) -> bool:
    """True for OpenAI/Gemini/Groq quota / rate-limit errors."""
    msg = str(exc).lower()
    return any(
        p in msg for p in (
            "insufficient_quota", "quota", "rate limit", "ratelimit",
            "resource_exhausted", "429", "billing",
        )
    )


def _is_auth_error(exc: Exception) -> bool:
    """True for invalid API key / auth errors."""
    msg = str(exc).lower()
    return any(p in msg for p in ("invalid_api_key", "api key", "authentication", "401", "403"))


def _no_llm_message() -> str:
    return (
        "ℹ️ **No LLM provider configured.**\n\n"
        "Set one of these in `backend/.env` to enable AI-generated answers:\n\n"
        "- **GEMINI_API_KEY** — Free at https://aistudio.google.com/apikey (recommended)\n"
        "- **GROQ_API_KEY** — Free at https://console.groq.com/keys (ultra-fast)\n"
        "- **OPENAI_API_KEY** — Paid at https://platform.openai.com\n\n"
        "BM25 keyword retrieval still works and document excerpts are shown below."
    )


def _bm25_answer_from_docs(
    context_blocks: list[tuple[str, str]],
    sources: list[dict],
    no_llm_message: str | None = None,
) -> str:
    """Compose a readable answer from retrieved document excerpts (no LLM required)."""
    header = no_llm_message or (
        "⚠️ **LLM generation unavailable** — showing raw retrieved excerpts.\n\n---"
    )
    lines = [header, "\n**What I found in the knowledge base:**\n"]
    for did, snip in context_blocks:
        title = next((s["title"] for s in sources if s["doc_id"] == did), did)
        excerpt = snip[:1500].strip()
        if len(snip) > 1500:
            excerpt += "…"
        lines.append(f"### {title}")
        lines.append(excerpt)
        lines.append("")
    return "\n".join(lines)


# ── Orchestrator ─────────────────────────────────────────────────────────────

@dataclass
class Orchestrator:
    records_by_id: dict[str, DocRecord]
    bm25: BM25Index
    chroma: Chroma
    chats: ChatRepository
    feedback: FeedbackRepository

    def _history_snippet(self, thread_id: str) -> str:
        msgs = self.chats.get_messages(thread_id, limit=10)
        lines: list[str] = []
        for m in msgs:
            role = m.get("role", "user")
            content = (m.get("content") or "")[:500]
            lines.append(f"{role}: {content}")
        return "\n".join(lines[-8:])

    def handle_message(self, thread_id: str | None, user_text: str) -> dict[str, Any]:
        trace: dict[str, Any] = {}
        thread_doc = self.chats.get_or_create_thread(thread_id)
        tid = thread_doc["thread_id"]
        try:
            return self._run_pipeline(tid, user_text, trace)
        except Exception as e:
            logger.exception("Chat pipeline failed (thread_id=%s)", tid)
            err = (
                "Something went wrong while processing your message. "
                f"Detail: {type(e).__name__}: {e}"
            )
            try:
                self.chats.append_message(tid, "user", user_text, {"stage": "user"})
                self.chats.append_message(
                    tid, "assistant", err,
                    {"stage": "error", "trace": trace if settings.debug_trace else {}},
                )
            except Exception:
                logger.exception("Could not persist error messages to MongoDB")
            err_trace: dict[str, Any] = dict(trace)
            if settings.debug_trace:
                err_trace["error"] = str(e)
                err_trace["error_type"] = type(e).__name__
            return {
                "thread_id": tid,
                "answer": err,
                "action": "error",
                "sources": [],
                "query_understanding": trace.get("query_understanding") or {},
                "trace": err_trace if settings.debug_trace else {},
            }

    def _run_pipeline(self, tid: str, user_text: str, trace: dict[str, Any]) -> dict[str, Any]:
        history = self._history_snippet(tid)
        provider = get_active_provider()
        trace["llm_provider"] = provider

        # ── Layer 1: Query understanding ─────────────────────────────
        if any_llm_configured() and settings.allow_llm_query_understanding:
            qu = llm_query_understanding(user_text, history)
        else:
            qu = heuristic_understanding(user_text)
        trace["query_understanding"] = qu.model_dump()

        # ── Agent decision ───────────────────────────────────────────
        decision = decide_agent_action(user_text, qu)
        trace["agent_decision"] = decision.model_dump()

        # ── Clarification path ───────────────────────────────────────
        if decision.action == "clarify":
            ref = llm_query_reformulation(user_text, qu, history)
            trace["reformulation"] = ref.model_dump()
            if ref.clarification_question:
                text = generate_clarification(ref.clarification_question, "What aspect should we focus on?")
            else:
                text = generate_clarification(None, "Could you specify which IR topic? (RAG, BM25, explainability…)")
            self.chats.append_message(tid, "user", user_text, {"stage": "user"})
            self.chats.append_message(tid, "assistant", text, {"stage": "clarify", "trace": trace if settings.debug_trace else {}})
            return {
                "thread_id": tid, "answer": text, "action": "clarify",
                "sources": [], "query_understanding": qu.model_dump(),
                "trace": trace if settings.debug_trace else {},
            }

        # ── Direct answer path ───────────────────────────────────────
        if decision.action == "direct":
            if not any_llm_configured():
                text = _no_llm_message()
            else:
                try:
                    text = generate_direct_answer(user_text)
                except Exception as de:
                    logger.warning("Direct chat completion failed (%s): %s", provider, de, exc_info=True)
                    if _is_quota_error(de) or _is_auth_error(de):
                        downgrade_provider(provider)  # type: ignore[arg-type]
                        new_provider = get_active_provider()
                        if new_provider != "none":
                            try:
                                text = generate_direct_answer(user_text)
                            except Exception:
                                text = _no_llm_message()
                        else:
                            text = (
                                f"⚠️ **{provider.capitalize()} quota/auth error.** "
                                "Try setting a different provider key in `backend/.env`:\n\n"
                                "- **GEMINI_API_KEY** → https://aistudio.google.com/apikey (free)\n"
                                "- **GROQ_API_KEY** → https://console.groq.com/keys (free, fast)\n"
                            )
                    else:
                        text = f"⚠️ Chat model error ({type(de).__name__}): {de}"
            self.chats.append_message(tid, "user", user_text, {"stage": "user"})
            self.chats.append_message(tid, "assistant", text, {"stage": "direct", "trace": trace if settings.debug_trace else {}})
            return {
                "thread_id": tid, "answer": text, "action": "direct",
                "sources": [], "query_understanding": qu.model_dump(),
                "trace": trace if settings.debug_trace else {},
            }

        # ── Retrieval + RAG path ─────────────────────────────────────
        ref = llm_query_reformulation(user_text, qu, history)
        trace["reformulation"] = ref.model_dump()
        q_retrieval = ref.expanded_query or user_text

        multidoc_summary = wants_multidoc_summary(qu.intent)
        trace["rag_mode"] = "summarize" if multidoc_summary else "answer"
        top_k_rank = (
            min(settings.top_k_summary, max(1, len(self.records_by_id)))
            if multidoc_summary
            else settings.top_k_final
        )
        top_k_vec = settings.top_k_vector
        top_k_bm = settings.top_k_bm25
        if multidoc_summary:
            top_k_vec = max(top_k_vec, top_k_rank + 2)
            top_k_bm = max(top_k_bm, top_k_rank + 2)

        hits = hybrid_retrieve(q_retrieval, self.bm25, self.chroma, top_k_bm, top_k_vec)
        trace["hybrid_candidates"] = len(hits)

        ranked = rank_and_explain(
            hits=hits, records_by_id=self.records_by_id, qu=qu,
            expanded_query=q_retrieval, feedback_repo=self.feedback, top_k=top_k_rank,
        )
        sources = format_sources_for_response(ranked)

        context_blocks: list[tuple[str, str]] = [
            (r.doc_id, (r.document.page_content or "")[:3500]) for r in ranked
        ]

        if not ranked:
            answer = (
                "No documents were retrieved. Add `.md` or `.pdf` files under `backend/data/docs/`, "
                "set `FORCE_REINDEX=true` once, and verify the Chroma index."
            )
            self._save(tid, user_text, answer, q_retrieval, [], "rag_empty", trace)
            return {
                "thread_id": tid, "answer": answer, "action": "retrieve",
                "sources": [], "query_understanding": qu.model_dump(),
                "expanded_query": q_retrieval,
                "trace": trace if settings.debug_trace else {},
            }

        # RAG generation
        if not any_llm_configured():
            answer = _bm25_answer_from_docs(context_blocks, sources, _no_llm_message())
        else:
            try:
                answer = generate_rag_answer(
                    user_text, context_blocks,
                    rag_mode="summarize" if multidoc_summary else "answer",
                )
            except Exception as gen_e:
                logger.warning("RAG generation failed (%s): %s", provider, gen_e, exc_info=True)
                if settings.debug_trace:
                    trace["rag_generation_error"] = f"{type(gen_e).__name__}: {gen_e}"

                if _is_quota_error(gen_e) or _is_auth_error(gen_e):
                    # Try next provider automatically
                    downgrade_provider(provider)  # type: ignore[arg-type]
                    new_provider = get_active_provider()
                    if new_provider != "none":
                        logger.info("Retrying RAG with fallback provider: %s", new_provider)
                        trace["llm_provider_fallback"] = new_provider
                        try:
                            answer = generate_rag_answer(
                                user_text, context_blocks,
                                rag_mode="summarize" if multidoc_summary else "answer",
                            )
                        except Exception as fallback_e:
                            logger.warning("Fallback provider also failed: %s", fallback_e)
                            answer = _bm25_answer_from_docs(context_blocks, sources)
                    else:
                        answer = _bm25_answer_from_docs(context_blocks, sources)
                else:
                    answer = (
                        f"⚠️ **Chat model error** ({type(gen_e).__name__}).\n\n"
                        "**Retrieved sources:**\n"
                        + "\n".join(f"- {s['title']} ({s['doc_id']}): {s['why']}" for s in sources)
                    )

        self._save(tid, user_text, answer, q_retrieval, sources, "rag", trace)
        return {
            "thread_id": tid,
            "answer": answer,
            "action": "retrieve",
            "sources": sources,
            "query_understanding": qu.model_dump(),
            "expanded_query": q_retrieval,
            "trace": trace if settings.debug_trace else {},
        }

    def _save(self, tid, user_text, answer, q_retrieval, sources, stage, trace):
        self.chats.append_message(tid, "user", user_text, {"stage": "user", "expanded_query": q_retrieval})
        self.chats.append_message(
            tid, "assistant", answer,
            {"stage": stage, "sources": sources, "trace": trace if settings.debug_trace else {}},
        )
