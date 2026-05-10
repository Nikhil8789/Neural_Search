"""Build or load the Chroma index; fill when empty, or rebuild when FORCE_REINDEX is set."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from langchain_core.documents import Document

from app.core.config import settings
from app.llm.openai_client import set_chroma_fake_embeddings_flag
from app.retrieval.corpus_loader import DocRecord, load_corpus
from app.retrieval.vectorstore import build_or_load_chroma

logger = logging.getLogger(__name__)

_COLLECTION = "ir_corpus"


def _delete_chroma_collection(persist: Path, name: str) -> None:
    client = chromadb.PersistentClient(path=str(persist))
    try:
        client.delete_collection(name)
    except Exception:
        pass


def records_to_documents(records: list[DocRecord]) -> list[Document]:
    docs: list[Document] = []
    for r in records:
        meta = {
            "doc_id": r.doc_id,
            "title": r.title,
            "source_path": r.source_path,
            **{k: v for k, v in r.metadata.items() if isinstance(v, (str, int, float, bool))},
        }
        docs.append(Document(page_content=r.text, metadata=meta))
    return docs


def ensure_index_built():
    base = Path(__file__).resolve().parents[2]
    corpus_dir = base / settings.corpus_dir
    meta_path = base / settings.corpus_metadata_path
    persist = (base / settings.chroma_persist_dir).resolve()
    persist.mkdir(parents=True, exist_ok=True)

    records = load_corpus(corpus_dir, meta_path)
    documents = records_to_documents(records)

    if settings.force_reindex and documents:
        _delete_chroma_collection(persist, _COLLECTION)
        set_chroma_fake_embeddings_flag(persist, False)

    store = build_or_load_chroma(persist, [], _COLLECTION)
    n = 0
    try:
        n = int(store._collection.count())
    except Exception:
        n = 0

    if documents and n == 0:
        try:
            store = build_or_load_chroma(persist, documents, _COLLECTION)
            set_chroma_fake_embeddings_flag(persist, False)
        except Exception as e:
            # OpenAI embeddings often fail with 429 insufficient_quota — still start the API
            # using deterministic fake embeddings; BM25 + RAG text gen can still work.
            logger.warning(
                "Chroma index build with OpenAI embeddings failed (%s: %s). "
                "Falling back to FakeEmbeddings; semantic search quality is reduced. "
                "Fix billing/quota or set FORCE_REINDEX=true after fixing to retry OpenAI embeddings.",
                type(e).__name__,
                e,
            )
            _delete_chroma_collection(persist, _COLLECTION)
            set_chroma_fake_embeddings_flag(persist, True)
            store = build_or_load_chroma(persist, documents, _COLLECTION)

    return records, store
