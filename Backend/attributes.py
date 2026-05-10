"""Attribute extraction for explainable matching (query + documents)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.llm.schemas import QueryUnderstanding
from app.retrieval.bm25 import tokenize
from app.retrieval.corpus_loader import DocRecord


@dataclass
class DocAttributes:
    doc_id: str
    keywords: list[str] = field(default_factory=list)
    metadata_tags: list[str] = field(default_factory=list)
    title_terms: list[str] = field(default_factory=list)


def query_attributes(qu: QueryUnderstanding) -> dict[str, list[str]]:
    """Flatten query understanding into attribute buckets for matching."""
    intent = qu.intent.lower().strip()
    entities = [e.lower() for e in qu.entities]
    constraints = [c.lower() for c in qu.constraints]
    ctx_terms = tokenize(qu.context_summary)[:20]
    return {
        "intent_terms": [intent] if intent else [],
        "entity_terms": entities,
        "constraint_terms": constraints,
        "context_terms": ctx_terms,
    }


def document_attributes(record: DocRecord) -> DocAttributes:
    meta = record.metadata or {}
    tags: list[str] = []
    for key in ("topics", "tags", "keywords"):
        val = meta.get(key)
        if isinstance(val, list):
            tags.extend(str(x).lower() for x in val)
        elif isinstance(val, str):
            tags.extend(tokenize(val))
    title_terms = tokenize(record.title)
    body_kw = tokenize(record.text)
    # cheap keyword selection: high freq tokens (cap)
    freq: dict[str, int] = {}
    for t in body_kw:
        if len(t) < 4:
            continue
        freq[t] = freq.get(t, 0) + 1
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:25]
    keywords = [w for w, _ in top]
    return DocAttributes(
        doc_id=record.doc_id,
        keywords=keywords,
        metadata_tags=list(dict.fromkeys(tags)),
        title_terms=title_terms,
    )


def attribute_sets_for_matching(da: DocAttributes) -> set[str]:
    return set(da.keywords + da.metadata_tags + da.title_terms)
