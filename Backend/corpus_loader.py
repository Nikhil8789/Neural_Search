"""Load markdown + PDF documents and optional metadata.jsonl."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.retrieval.pdf_text import extract_pdf_text


@dataclass
class DocRecord:
    doc_id: str
    title: str
    text: str
    source_path: str
    metadata: dict


def load_metadata_map(metadata_path: Path) -> dict[str, dict]:
    if not metadata_path.exists():
        return {}
    out: dict[str, dict] = {}
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        doc_id = row.get("doc_id")
        if doc_id:
            out[doc_id] = row
    return out


def _corpus_file_paths(corpus_dir: Path) -> list[Path]:
    """Stable order: all .md then all .pdf (by name) so doc_id stems are predictable."""
    md = sorted(corpus_dir.glob("*.md"), key=lambda p: p.name.lower())
    pdf = sorted(corpus_dir.glob("*.pdf"), key=lambda p: p.name.lower())
    return md + pdf


def load_corpus(corpus_dir: Path, metadata_path: Path) -> list[DocRecord]:
    meta = load_metadata_map(metadata_path)
    records: list[DocRecord] = []
    if not corpus_dir.exists():
        return records
    for path in _corpus_file_paths(corpus_dir):
        doc_id = path.stem
        suffix = path.suffix.lower()
        if suffix == ".md":
            text = path.read_text(encoding="utf-8")
            source_type = "markdown"
        elif suffix == ".pdf":
            text = extract_pdf_text(path)
            source_type = "pdf"
        else:
            continue
        m = meta.get(doc_id, {})
        title = m.get("title", doc_id.replace("_", " ").title())
        records.append(
            DocRecord(
                doc_id=doc_id,
                title=title,
                text=text,
                source_path=str(path),
                metadata={**m, "filename": path.name, "source_type": source_type},
            )
        )
    return records
