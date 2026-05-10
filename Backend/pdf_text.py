"""Extract plain text from PDF files for indexing (pypdf)."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    text = "\n\n".join(parts).strip()
    if not text:
        return "[No extractable text from this PDF; it may be scanned or image-only.]"
    return text
