"""LLM answer generation (RAG + direct)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.openai_client import get_chat
from app.rag.prompts import (
    SYSTEM_DIRECT,
    SYSTEM_RAG,
    SYSTEM_RAG_MULTIDOC_SUMMARY,
    build_multidoc_summary_user_prompt,
    build_rag_user_prompt,
)


def generate_rag_answer(
    question: str,
    context_blocks: list[tuple[str, str]],
    model: str | None = None,
    *,
    rag_mode: str = "answer",
) -> str:
    """
    rag_mode:
      - "answer" — standard grounded QA
      - "summarize" — explicit multi-document synthesis prompt
    """
    llm = get_chat(model=model, temperature=0.2 if rag_mode == "answer" else 0.25)
    if rag_mode == "summarize":
        system = SYSTEM_RAG_MULTIDOC_SUMMARY
        msg = build_multidoc_summary_user_prompt(question, context_blocks)
    else:
        system = SYSTEM_RAG
        msg = build_rag_user_prompt(question, context_blocks)
    out = llm.invoke([SystemMessage(content=system), HumanMessage(content=msg)])
    return str(out.content)


def generate_direct_answer(question: str, model: str | None = None) -> str:
    llm = get_chat(model=model, temperature=0.35)
    out = llm.invoke(
        [SystemMessage(content=SYSTEM_DIRECT), HumanMessage(content=question)]
    )
    return str(out.content)


def generate_clarification(clarification_question: str | None, fallback: str) -> str:
    return clarification_question.strip() if clarification_question else fallback
