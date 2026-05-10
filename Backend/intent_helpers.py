"""Intent normalization for routing (e.g. multi-document RAG summarization)."""

from __future__ import annotations

_EXACT_SUMMARY = frozenset(
    {
        "summarize",
        "summary",
        "multi_doc_summary",
        "multi_document_summary",
        "synthesis",
        "tl_dr",
    }
)


def wants_multidoc_summary(intent: str) -> bool:
    """True when the understood intent calls for synthesizing multiple retrieved sources."""
    i = (intent or "").strip().lower()
    if not i:
        return False
    if i in _EXACT_SUMMARY:
        return True
    if "summar" in i:
        return True
    if "synthesis" in i or "synthesize" in i:
        return True
    return False
