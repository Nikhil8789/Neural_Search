"""
Multi-provider LLM client.

Priority order (when llm_provider=auto):
  1. OpenAI     — if OPENAI_API_KEY is set and quota is not exhausted
  2. Gemini     — if GEMINI_API_KEY is set  (free, has embeddings)
  3. Groq       — if GROQ_API_KEY  is set  (free, ultra-fast, no embeddings)
  4. None       — BM25-only fallback (no RAG generation)

Use environment variable LLM_PROVIDER to force a specific provider.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from langchain_community.embeddings import FakeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Chroma fake-embedding flag file ─────────────────────────────────────────
_FAKE_CHROMA_MARKER = ".chroma_fake_embeddings"


def chroma_flagged_fake_embeddings(persist_dir: Path | str) -> bool:
    return (Path(persist_dir) / _FAKE_CHROMA_MARKER).is_file()


def set_chroma_fake_embeddings_flag(persist_dir: Path | str, use_fake: bool) -> None:
    root = Path(persist_dir)
    root.mkdir(parents=True, exist_ok=True)
    flag = root / _FAKE_CHROMA_MARKER
    if use_fake:
        flag.write_text("1", encoding="utf-8")
    elif flag.exists():
        flag.unlink()


# ── Key validators ───────────────────────────────────────────────────────────

def openai_key_looks_configured() -> bool:
    k = (settings.openai_api_key or "").strip()
    if len(k) < 20:
        return False
    low = k.lower()
    return not any(
        p in low
        for p in ("your_openai", "your-openai", "your_api", "placeholder",
                  "changeme", "replace_me", "insert_key", "sk-xxxxx")
    )


def gemini_key_looks_configured() -> bool:
    k = (settings.gemini_api_key or "").strip()
    return len(k) >= 20 and not any(
        p in k.lower() for p in ("your_", "placeholder", "changeme")
    )


def groq_key_looks_configured() -> bool:
    k = (settings.groq_api_key or "").strip()
    return len(k) >= 20 and not any(
        p in k.lower() for p in ("your_", "placeholder", "changeme")
    )


# ── Active provider detection ────────────────────────────────────────────────

Provider = Literal["openai", "gemini", "groq", "none"]

# Cache after first resolution (may be overridden by quota detection)
_resolved_provider: Provider | None = None


def _resolve_provider() -> Provider:
    """Pick the best available provider based on LLM_PROVIDER env and key presence."""
    forced = (settings.llm_provider or "auto").lower().strip()

    if forced == "openai":
        return "openai" if openai_key_looks_configured() else "none"
    if forced == "gemini":
        return "gemini" if gemini_key_looks_configured() else "none"
    if forced == "groq":
        return "groq" if groq_key_looks_configured() else "none"

    # auto — try in priority order
    if openai_key_looks_configured():
        return "openai"
    if gemini_key_looks_configured():
        return "gemini"
    if groq_key_looks_configured():
        return "groq"
    return "none"


def get_active_provider() -> Provider:
    """Return the resolved provider (cached after first call)."""
    global _resolved_provider
    if _resolved_provider is None:
        _resolved_provider = _resolve_provider()
        logger.info("LLM provider resolved: %s", _resolved_provider)
    return _resolved_provider


def downgrade_provider(failed_provider: Provider) -> None:
    """
    Called when a provider fails with a quota/auth error.
    Falls through to the next available provider.
    """
    global _resolved_provider
    order: list[Provider] = ["openai", "gemini", "groq", "none"]
    try:
        idx = order.index(failed_provider)
    except ValueError:
        idx = -1

    for candidate in order[idx + 1:]:
        if candidate == "none":
            _resolved_provider = "none"
            break
        if candidate == "gemini" and gemini_key_looks_configured():
            logger.warning("Downgrading from %s → gemini", failed_provider)
            _resolved_provider = "gemini"
            break
        if candidate == "groq" and groq_key_looks_configured():
            logger.warning("Downgrading from %s → groq", failed_provider)
            _resolved_provider = "groq"
            break
    else:
        _resolved_provider = "none"

    logger.info("New active LLM provider: %s", _resolved_provider)


def any_llm_configured() -> bool:
    return get_active_provider() != "none"


# ── Chat model factory ───────────────────────────────────────────────────────

def get_chat(model: str | None = None, temperature: float = 0.2) -> BaseChatModel:
    """Return a chat model for the active provider."""
    provider = get_active_provider()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or settings.openai_model,
            temperature=temperature,
            api_key=settings.openai_api_key,
            max_retries=0,  # fail fast on quota errors
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            temperature=temperature,
            google_api_key=settings.gemini_api_key,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model or settings.groq_model,
            temperature=temperature,
            groq_api_key=settings.groq_api_key,
        )

    raise RuntimeError("No LLM provider configured. Set GEMINI_API_KEY or GROQ_API_KEY in backend/.env")


# ── Embeddings factory ───────────────────────────────────────────────────────

def get_embeddings(persist_dir: Path | str | None = None) -> Embeddings:
    """
    Return an embeddings model.

    Priority:
      1. If Chroma was built with FakeEmbeddings → keep using FakeEmbeddings
         (dimension mismatch if we switch)
      2. OpenAI embeddings (if configured)
      3. Gemini embeddings (if configured) — free
      4. FakeEmbeddings fallback (Groq has no embedding API)
    """
    if persist_dir is not None and chroma_flagged_fake_embeddings(persist_dir):
        return FakeEmbeddings(size=384)

    if openai_key_looks_configured():
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(api_key=settings.openai_api_key)

    if gemini_key_looks_configured():
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=settings.gemini_api_key,
        )

    # Groq / no provider → FakeEmbeddings (BM25 still works fine)
    return FakeEmbeddings(size=384)
