"""Chroma vector store + embedding-backed similarity."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.llm.openai_client import get_embeddings


def build_or_load_chroma(
    persist_dir: str | Path,
    documents: list[Document],
    collection_name: str = "ir_corpus",
) -> Chroma:
    path = Path(persist_dir)
    path.mkdir(parents=True, exist_ok=True)
    emb = get_embeddings(path)
    if documents:
        return Chroma.from_documents(
            documents=documents,
            embedding=emb,
            persist_directory=str(path),
            collection_name=collection_name,
        )
    return Chroma(
        persist_directory=str(path),
        embedding_function=emb,
        collection_name=collection_name,
    )


def similarity_search_with_score(store: Chroma, query: str, k: int) -> list[tuple[Document, float]]:
    # Chroma returns distance; convert to similarity-like score in hybrid layer if needed
    return store.similarity_search_with_score(query, k=k)
