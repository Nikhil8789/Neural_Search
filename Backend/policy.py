"""Agent policy: direct answer vs retrieval vs clarification (rules + optional LLM)."""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.intent_helpers import wants_multidoc_summary
from app.core.config import settings
from app.llm.openai_client import any_llm_configured, get_chat
from app.llm.schemas import AgentDecision, QueryUnderstanding

_SIMPLE_GREETING = re.compile(
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks|thank you|what's up|sup)[\s!.?]*$",
    re.I,
)
_SHORT_OPINION = re.compile(r"^\s*(what do you think|in your opinion)", re.I)
_GENERAL_WHO_IS = re.compile(r"^\s*who\s+is\s+.", re.I)
_GENERAL_DEFINE = re.compile(r"^\s*define\s+.", re.I)

# IR / RAG domain terms — any of these present → always retrieve from corpus
_IR_TERMS = (
    "rag",
    "retriev",
    "bm25",
    "embedding",
    "vector",
    "index",
    "rank",
    "ranking",
    "information retrieval",
    "hallucination",
    "grounding",
    "ground truth",
    "citation",
    "explainab",
    "feedback",
    "hybrid",
    "langchain",
    "chromadb",
    "chroma",
    "faiss",
    "mongo",
    "pydantic",
    "semantic search",
    "dense retrieval",
    "sparse retrieval",
    "query expansion",
    "rerank",
    "recall",
    "precision",
    "f1 score",
    "ndcg",
    "mrr",
    "relevance",
    "llm",
    "large language model",
    "generation",
    "augmented",
    "knowledge base",
)

# These intents ALWAYS mean "retrieve from corpus" — never clarify
_ALWAYS_RETRIEVE_INTENTS = frozenset(
    {
        "explain",
        "explain_concept",
        "compare",
        "compare_methods",
        "define",
        "list_steps",
        "procedural",
        "how_to",
        "describe",
        "overview",
        "summarize",
        "synthesis",
    }
)

_DIRECT_SKIP_LLM_MERGE = frozenset(
    {
        "general_knowledge_question",
        "greeting_or_social",
        "subjective_opinion_style",
    }
)


def rule_based_decision(user_text: str, qu: QueryUnderstanding) -> AgentDecision:
    text = user_text.strip()

    # Tiny input
    if len(text) < 3:
        return AgentDecision(action="clarify", reason="empty_or_tiny", confidence=0.9)

    lower = text.lower()

    # Greetings
    if _SIMPLE_GREETING.match(text):
        return AgentDecision(action="direct", reason="greeting_or_social", confidence=0.95)

    # Multi-doc summary intent
    if wants_multidoc_summary(qu.intent):
        return AgentDecision(
            action="retrieve",
            reason="summarize_or_synthesize_requires_corpus",
            confidence=0.92,
        )

    # IR domain terms → ALWAYS retrieve (never clarify)
    if any(t in lower for t in _IR_TERMS):
        return AgentDecision(action="retrieve", reason="domain_terms_detected", confidence=0.90)

    # Intent is clearly 'explain', 'compare', 'define', etc. → retrieve
    intent_lower = (qu.intent or "").lower()
    if any(intent_lower.startswith(i) or i in intent_lower for i in _ALWAYS_RETRIEVE_INTENTS):
        return AgentDecision(
            action="retrieve",
            reason=f"retrieve_intent_{intent_lower}",
            confidence=0.85,
        )

    # Has entities in the query → likely specific enough to retrieve
    if qu.entities and len(qu.entities) >= 1:
        return AgentDecision(
            action="retrieve",
            reason="entities_present",
            confidence=0.80,
        )

    # Questions with "what", "how", "why", "when", "explain" → retrieve if >= 5 words
    question_words = ("what", "how", "why", "when", "which", "explain", "describe", "compare", "list")
    if any(lower.startswith(w) for w in question_words) and len(text.split()) >= 5:
        return AgentDecision(
            action="retrieve",
            reason="substantive_question",
            confidence=0.80,
        )

    # General trivia / who-is / define → direct (no corpus needed)
    if _GENERAL_WHO_IS.match(text) or _GENERAL_DEFINE.match(text):
        return AgentDecision(
            action="direct",
            reason="general_knowledge_question",
            confidence=0.72,
        )

    # Opinion
    if _SHORT_OPINION.match(text):
        return AgentDecision(action="direct", reason="subjective_opinion_style", confidence=0.65)

    # Very short + no entities → clarify as last resort
    if len(text.split()) <= 3 and not qu.entities:
        return AgentDecision(action="clarify", reason="short_and_missing_entities", confidence=0.55)

    # Default: retrieve (grounded assistant persona)
    return AgentDecision(action="retrieve", reason="default_grounded_mode", confidence=0.70)


def llm_decision(user_text: str, qu: QueryUnderstanding) -> AgentDecision | None:
    """Ask the LLM to decide. Returns None on failure or when LLM is not configured."""
    if not any_llm_configured():
        return None
    try:
        llm = get_chat(temperature=0)
        structured = llm.with_structured_output(AgentDecision)
        result = structured.invoke(
            [
                SystemMessage(
                    content=(
                        "You control an IR+RAG research assistant. "
                        "Decide the action for this user message.\n"
                        "Rules:\n"
                        "- 'retrieve': user is asking about IR, RAG, BM25, embeddings, ranking, "
                        "explainability, feedback, LLMs, or any research topic → ALWAYS retrieve.\n"
                        "- 'direct': generic greeting, opinion, or clearly off-topic question.\n"
                        "- 'clarify': ONLY if the message is completely ambiguous with NO topic "
                        "whatsoever (e.g. a single word like 'it' or 'that').\n"
                        "IMPORTANT: questions about IR topics (even general ones like "
                        "'what is explainable ranking') should ALWAYS be 'retrieve'.\n"
                        "Return JSON only."
                    )
                ),
                HumanMessage(
                    content=(
                        f"User message:\n{user_text}\n\n"
                        f"Parsed understanding:\n"
                        f"intent={qu.intent}\nentities={qu.entities}\nconstraints={qu.constraints}\n"
                        f"context_summary={qu.context_summary}\n"
                    )
                ),
            ]
        )
        if isinstance(result, AgentDecision):
            return result
        return AgentDecision.model_validate(result)
    except Exception:
        return None


def decide_agent_action(user_text: str, qu: QueryUnderstanding) -> AgentDecision:
    rules = rule_based_decision(user_text, qu)

    # Rules already gave a confident retrieve → trust it, skip LLM
    if rules.action == "retrieve" and rules.confidence >= 0.80:
        return rules

    # Fast-path for unambiguous social/greeting
    if rules.action == "direct" and rules.reason in _DIRECT_SKIP_LLM_MERGE:
        return rules

    # No LLM available → use rules
    if not any_llm_configured() or not settings.allow_llm_query_understanding:
        return rules

    llm_d = llm_decision(user_text, qu)
    if llm_d is None:
        return rules

    # --- Merge ---
    # If BOTH say retrieve → retrieve
    if rules.action == "retrieve" and llm_d.action == "retrieve":
        return AgentDecision(
            action="retrieve",
            reason=f"merged(rules={rules.reason}, llm={llm_d.reason})",
            confidence=max(rules.confidence, llm_d.confidence),
        )

    # If rules say retrieve → trust rules over LLM clarify
    if rules.action == "retrieve":
        return rules

    # If LLM says retrieve → follow LLM
    if llm_d.action == "retrieve":
        return llm_d

    # Only clarify when BOTH agree it's ambiguous AND rules confidence is low
    if rules.action == "clarify" and llm_d.action == "clarify" and rules.confidence < 0.65:
        return AgentDecision(
            action="clarify",
            reason=f"merged(rules={rules.reason}, llm={llm_d.reason})",
            confidence=min(rules.confidence, llm_d.confidence),
        )

    # If LLM says direct and rules say direct → direct
    if llm_d.action == "direct" and rules.action == "direct":
        return llm_d

    # If LLM says direct and rules are neutral → follow LLM
    if llm_d.action == "direct" and rules.action != "retrieve":
        return llm_d

    # Default fallback → retrieve (better to over-retrieve than to clarify everything)
    return AgentDecision(action="retrieve", reason="fallback_retrieve", confidence=0.65)
