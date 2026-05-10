"""BM25 keyword index over corpus tokens."""

from __future__ import annotations

import re
from typing import Iterable

from rank_bm25 import BM25Okapi


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class BM25Index:
    def __init__(self, docs: list[tuple[str, str]]) -> None:
        """
        docs: list of (doc_id, full_text)
        """
        self.doc_ids: list[str] = []
        self.tokenized_corpus: list[list[str]] = []
        for doc_id, text in docs:
            self.doc_ids.append(doc_id)
            self.tokenized_corpus.append(tokenize(text))
        self._bm25 = BM25Okapi(self.tokenized_corpus) if self.tokenized_corpus else None

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        if not self._bm25:
            return []
        q = tokenize(query)
        scores = self._bm25.get_scores(q)
        ranked = sorted(zip(self.doc_ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def keyword_overlap_score(self, query: str, doc_text: str) -> float:
        """Normalized overlap: |Q ∩ D| / max(1, |Q|)."""
        q_set = set(tokenize(query))
        d_set = set(tokenize(doc_text))
        if not q_set:
            return 0.0
        inter = len(q_set & d_set)
        return min(1.0, inter / max(1, len(q_set)))
