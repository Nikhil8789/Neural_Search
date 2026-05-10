"""Prompt templates for RAG and direct answers."""

SYSTEM_RAG = """You are a research assistant for Information Retrieval (IR) and Large Language Models.
Use ONLY the provided CONTEXT snippets to answer. If context is insufficient, say what is missing and suggest what to retrieve.
Always cite sources using [doc_id] inline where you use a fact from that snippet.
Be concise but precise; prefer bullet lists for multi-part answers."""

SYSTEM_RAG_MULTIDOC_SUMMARY = """You are a research assistant specializing in Information Retrieval (IR) and LLMs.
The user wants a MULTI-DOCUMENT grounded summary. You are given several CONTEXT blocks from different doc_ids.

Rules:
- Use ONLY information present in CONTEXT. Do not use outside knowledge.
- Synthesize across documents: group by theme; note where sources agree or differ.
- Every non-trivial claim must cite [doc_id] inline.
- Prefer structured output: short intro, themed sections, then a compact bullet list of takeaways.
- Finish with a line exactly like: Sources consulted: [doc_id1, doc_id2, ...] using only ids you actually used.
- If a document adds nothing relevant, omit it (do not cite it)."""

SYSTEM_DIRECT = """You are a helpful assistant. Answer clearly. For domain-specific factual claims about the course corpus,
note that you are not retrieving documents unless the user asked for grounded citations."""


def build_rag_user_prompt(question: str, context_blocks: list[tuple[str, str]]) -> str:
    """
    context_blocks: list of (doc_id, snippet_text)
    """
    parts = [f"QUESTION:\n{question}\n", "CONTEXT:\n"]
    for doc_id, snippet in context_blocks:
        parts.append(f"--- BEGIN {doc_id} ---\n{snippet}\n--- END {doc_id} ---\n")
    parts.append("\nAnswer with citations [doc_id].")
    return "\n".join(parts)


def build_multidoc_summary_user_prompt(question: str, context_blocks: list[tuple[str, str]]) -> str:
    parts = [
        f"USER REQUEST (multi-document summary / synthesis):\n{question}\n",
        "CONTEXT (multiple documents; each block is independent):\n",
    ]
    for doc_id, snippet in context_blocks:
        parts.append(f"--- BEGIN {doc_id} ---\n{snippet}\n--- END {doc_id} ---\n")
    parts.append(
        "\nWrite the grounded multi-document summary following the system instructions. "
        "Cite [doc_id] throughout and end with Sources consulted: [...]."
    )
    return "\n".join(parts)
