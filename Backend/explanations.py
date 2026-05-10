"""Human-readable retrieval explanations for UI + viva demos."""


def retrieval_why_line(matched_attributes: list[str]) -> str:
    if not matched_attributes:
        return "Document retrieved primarily due to semantic/keyword fusion scores."
    attrs = "; ".join(matched_attributes[:6])
    return f"Document retrieved because it matches: {attrs}"


def format_sources_for_response(ranked: list) -> list[dict]:
    out = []
    for r in ranked:
        md = r.document.metadata or {}
        out.append(
            {
                "doc_id": r.doc_id,
                "title": md.get("title", r.doc_id),
                "explanation": r.explanation,
                "why": retrieval_why_line(r.matched_attributes),
                "scores": {
                    "final": round(r.final_score, 4),
                    "keyword": round(r.keyword_score, 4),
                    "semantic": round(r.semantic_score, 4),
                    "attribute": round(r.attribute_score, 4),
                    "feedback_boost": round(r.feedback_boost, 4),
                },
                "matched_attributes": r.matched_attributes,
            }
        )
    return out
