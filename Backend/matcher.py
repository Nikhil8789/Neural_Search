"""Explainable ranking: keyword + semantic + attribute match + feedback boost."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from app.db.repositories import FeedbackRepository
from app.explain.attributes import DocAttributes, attribute_sets_for_matching, document_attributes, query_attributes
from app.llm.schemas import QueryUnderstanding
from app.retrieval.corpus_loader import DocRecord
from app.retrieval.hybrid import HybridHit


@dataclass
class RankedDoc:
    doc_id: str
    document: Document
    final_score: float
    keyword_score: float
    semantic_score: float
    attribute_score: float
    feedback_boost: float
    matched_attributes: list[str]
    explanation: str


def _overlap_score(query_set: set[str], doc_set: set[str]) -> float:
    if not query_set:
        return 0.0
    inter = query_set & doc_set
    return min(1.0, len(inter) / max(1, len(query_set)))


def rank_and_explain(
    hits: list[HybridHit],
    records_by_id: dict[str, DocRecord],
    qu: QueryUnderstanding,
    expanded_query: str,
    feedback_repo: FeedbackRepository | None,
    top_k: int,
) -> list[RankedDoc]:
    q_attrs = query_attributes(qu)
    flat_q = set()
    for bucket in q_attrs.values():
        flat_q.update(bucket)
    # include expanded query tokens
    from app.retrieval.bm25 import tokenize

    flat_q.update(tokenize(expanded_query))

    ranked: list[RankedDoc] = []
    for h in hits:
        rec = records_by_id.get(h.doc_id)
        if not rec:
            continue
        doc = h.document or Document(
            page_content=rec.text,
            metadata={"doc_id": rec.doc_id, "title": rec.title},
        )
        da = document_attributes(rec)
        doc_set = attribute_sets_for_matching(da)

        kw = 0.6 * h.bm25_score + 0.4 * h.vec_similarity
        sem = h.vec_similarity
        attr = _overlap_score(flat_q, doc_set)

        boost = 0.0
        if feedback_repo:
            stats = feedback_repo.doc_feedback_stats(h.doc_id)
            # small bounded boost from net likes
            net = stats["likes"] - stats["dislikes"]
            boost = max(-0.15, min(0.15, 0.02 * net))

        final = 0.35 * kw + 0.35 * sem + 0.30 * attr + boost

        matched: list[str] = []
        for label, terms in q_attrs.items():
            if not terms:
                continue
            ts = set(terms)
            inter = ts & doc_set
            if inter:
                matched.append(f"{label}:{','.join(sorted(inter)[:5])}")

        # keyword overlap explanation snippet
        q_tokens = set(tokenize(expanded_query))
        d_tokens = set(tokenize(doc.page_content[:4000]))
        overlap_kw = sorted(q_tokens & d_tokens)[:8]
        if overlap_kw:
            matched.append(f"keyword_overlap:{','.join(overlap_kw)}")

        expl = (
            f"Document ranked highly due to blend of keyword IR (BM25 norm={h.bm25_score:.2f}), "
            f"semantic similarity (~{h.vec_similarity:.2f}), and attribute overlap ({attr:.2f})."
        )
        if boost != 0:
            expl += f" User feedback adjusted score by {boost:+.2f}."

        ranked.append(
            RankedDoc(
                doc_id=h.doc_id,
                document=doc,
                final_score=final,
                keyword_score=kw,
                semantic_score=sem,
                attribute_score=attr,
                feedback_boost=boost,
                matched_attributes=matched,
                explanation=expl,
            )
        )

    ranked.sort(key=lambda x: x.final_score, reverse=True)
    return ranked[:top_k]
