"""Fuse BM25 and vector hits into a deduped candidate set with coarse scores."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.retrieval.bm25 import BM25Index


@dataclass
class HybridHit:
    doc_id: str
    document: Document | None
    bm25_score: float
    vec_distance: float | None
    vec_similarity: float


def _doc_by_id(docs: list[Document]) -> dict[str, Document]:
    out: dict[str, Document] = {}
    for d in docs:
        did = d.metadata.get("doc_id")
        if did:
            out[str(did)] = d
    return out


def hybrid_retrieve(
    query: str,
    bm25: BM25Index,
    chroma: Chroma,
    top_k_bm25: int,
    top_k_vec: int,
) -> list[HybridHit]:
    bm25_hits = bm25.search(query, top_k_bm25)
    vec_results = chroma.similarity_search_with_score(query, k=top_k_vec)

    id_to_doc = _doc_by_id([d for d, _ in vec_results])
    # also include docs from BM25 only: fetch by scanning is expensive; use vec doc set + bm25 ids
    merged: dict[str, HybridHit] = {}

    for doc_id, s in bm25_hits:
        merged[doc_id] = HybridHit(
            doc_id=doc_id,
            document=id_to_doc.get(doc_id),
            bm25_score=float(s),
            vec_distance=None,
            vec_similarity=0.0,
        )

    for doc, dist in vec_results:
        did = str(doc.metadata.get("doc_id", ""))
        if not did:
            continue
        # Chroma L2 distance: smaller is better; map to similarity
        sim = 1.0 / (1.0 + float(dist))
        if did in merged:
            h = merged[did]
            h.vec_distance = float(dist)
            h.vec_similarity = sim
            if h.document is None:
                h.document = doc
        else:
            merged[did] = HybridHit(
                doc_id=did,
                document=doc,
                bm25_score=0.0,
                vec_distance=float(dist),
                vec_similarity=sim,
            )

    # Normalize bm25 per batch (max)
    max_b = max((h.bm25_score for h in merged.values()), default=1.0) or 1.0
    for h in merged.values():
        h.bm25_score = min(1.0, h.bm25_score / max_b)

    return list(merged.values())
