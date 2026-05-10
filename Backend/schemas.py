"""Structured outputs from LLM stages (query understanding, reformulation)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryUnderstanding(BaseModel):
    intent: str = Field(description="short intent label, e.g. compare, explain, summarize, list_sources")
    entities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list, description="must-have facets, years, definitions")
    context_summary: str = Field(default="", description="1–2 sentences of conversational context")


class QueryReformulation(BaseModel):
    expanded_query: str = Field(description="query with synonyms/expansion for retrieval")
    clarification_question: str | None = Field(
        default=None,
        description="If missing critical info, one short question; else null",
    )


class AgentDecision(BaseModel):
    action: str = Field(description="one of: direct, retrieve, clarify")
    reason: str = Field(default="")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
