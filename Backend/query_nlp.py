"""LLM-based query understanding and reformulation."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.llm.openai_client import any_llm_configured, get_chat
from app.llm.schemas import QueryReformulation, QueryUnderstanding


def heuristic_understanding(user_text: str) -> QueryUnderstanding:
    """Fallback when API key missing or LLM fails."""
    lower = user_text.lower()
    intent = "explain"
    if any(w in lower for w in ("compare", "vs", "versus")):
        intent = "compare"
    if any(w in lower for w in ("summarize", "summary", "tl;dr")):
        intent = "summarize"
    if any(w in lower for w in ("list", "steps", "how do")):
        intent = "procedural"
    entities: list[str] = []
    for key in ("rag", "bm25", "embedding", "llm", "chromadb", "faiss", "mongodb", "langchain"):
        if key in lower.replace(" ", ""):
            entities.append(key)
    constraints: list[str] = []
    if "202" in user_text:
        constraints.append("time_reference")
    # Do not inject fake entities: that skipped short-query clarify and forced irrelevant RAG.
    return QueryUnderstanding(
        intent=intent,
        entities=entities,
        constraints=constraints,
        context_summary="",
    )


def llm_query_understanding(user_text: str, history_snippet: str) -> QueryUnderstanding:
    if not any_llm_configured() or not settings.allow_llm_query_understanding:
        return heuristic_understanding(user_text)
    try:
        llm = get_chat(temperature=0)
        structured = llm.with_structured_output(QueryUnderstanding)
        result = structured.invoke(
            [
                SystemMessage(
                    content=(
                        "Extract structured query understanding for an IR+RAG system. "
                        "intent: one short verb-noun label. entities: key nouns/phrases. "
                        "constraints: hard requirements (definitions, dates, 'must include'). "
                        "context_summary: 1-2 sentences merging prior turns if any."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Conversation snippet (last turns):\n{history_snippet}\n\n"
                        f"Latest user message:\n{user_text}\n"
                    )
                ),
            ]
        )
        if isinstance(result, QueryUnderstanding):
            return result
        return QueryUnderstanding.model_validate(result)
    except Exception:
        return heuristic_understanding(user_text)


def llm_query_reformulation(
    user_text: str,
    qu: QueryUnderstanding,
    history_snippet: str,
) -> QueryReformulation:
    if not any_llm_configured() or not settings.allow_llm_query_reformulation:
        return QueryReformulation(
            expanded_query=user_text,
            clarification_question=None,
        )
    try:
        llm = get_chat(temperature=0.15)
        structured = llm.with_structured_output(QueryReformulation)
        result = structured.invoke(
            [
                SystemMessage(
                    content=(
                        "Reformulate the user query for hybrid retrieval (BM25 + dense). "
                        "expanded_query: add synonyms and expansion terms; keep it one paragraph max. "
                        "clarification_question: ask ONLY if a critical missing slot blocks retrieval; else null."
                    )
                ),
                HumanMessage(
                    content=(
                        f"History:\n{history_snippet}\n\n"
                        f"User:\n{user_text}\n\n"
                        f"Understanding:\n{qu.model_dump_json()}\n"
                    )
                ),
            ]
        )
        if isinstance(result, QueryReformulation):
            return result
        return QueryReformulation.model_validate(result)
    except Exception:
        return QueryReformulation(expanded_query=user_text, clarification_question=None)
