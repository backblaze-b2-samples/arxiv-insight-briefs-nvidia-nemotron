"""NL question -> structured arxiv query (categories + keywords + window).

Falls back to a permissive cs.* keyword search when the LLM is unavailable
or returns nothing usable. The fallback is what makes the sample usable
without an NVIDIA API key (one of the failure modes the plan calls out).
"""

from __future__ import annotations

import logging

from app.config import settings
from app.repo import arxiv_taxonomy, nemotron_client
from app.service.prompts import ROUTER_SYSTEM, build_router_user
from app.types import ResolvedQuery

logger = logging.getLogger(__name__)


def resolve_query(question: str, override_window: int | None) -> ResolvedQuery:
    """Return a validated ResolvedQuery, never raising on LLM trouble.

    The fallback path produces a usable keyword-only query so the rest of
    the pipeline still has something to search for.
    """
    window = override_window or settings.brief_time_window_months

    try:
        completion = nemotron_client.chat_completion(
            system=ROUTER_SYSTEM,
            user=build_router_user(question, window),
            temperature=0.1,
            max_tokens=400,
            response_format_json=True,
        )
    except nemotron_client.NemotronNotConfigured:
        logger.info("topic_router: no NVIDIA key, using keyword fallback")
        return _fallback(question, window, reason="nvidia_not_configured")
    except nemotron_client.NemotronError as e:
        logger.warning("topic_router: nemotron error after retries: %s", e)
        return _fallback(question, window, reason=f"llm_error: {e}")

    text = nemotron_client.extract_text(completion)
    payload = nemotron_client.parse_json_or_none(text)
    if not isinstance(payload, dict):
        logger.warning("topic_router: non-JSON response, using keyword fallback")
        return _fallback(question, window, reason="llm_non_json")

    raw_categories = payload.get("categories") or []
    raw_keywords = payload.get("keywords") or []
    raw_window = payload.get("time_window_months")

    categories, dropped = arxiv_taxonomy.filter_valid(
        [c for c in raw_categories if isinstance(c, str)]
    )
    keywords = [k for k in raw_keywords if isinstance(k, str) and k.strip()]
    try:
        resolved_window = int(raw_window) if raw_window is not None else window
    except (TypeError, ValueError):
        resolved_window = window
    resolved_window = max(1, min(120, resolved_window))

    warnings: list[str] = []
    if dropped:
        warnings.append(f"dropped invalid categories: {', '.join(dropped)}")
    if not categories:
        # All hallucinated — fall back to the cs.* prefix so the search step
        # still has a category clause but doesn't over-constrain.
        warnings.append("router returned no valid categories; defaulting to cs.*")
        categories = ["cs"]

    return ResolvedQuery(
        question=question,
        categories=categories,
        keywords=keywords[:6],  # cap to keep the search query bounded
        time_window_months=resolved_window,
        fallback_used=False,
        warnings=warnings,
    )


def _fallback(question: str, window: int, *, reason: str) -> ResolvedQuery:
    """Build a permissive keyword search across cs.* from the raw question."""
    keywords = _naive_keywords(question)
    return ResolvedQuery(
        question=question,
        categories=["cs"],
        keywords=keywords,
        time_window_months=window,
        fallback_used=True,
        warnings=[f"router skipped ({reason}); using keyword fallback"],
    )


# A tiny stopword list — just enough to keep the fallback keyword query useful.
_STOP = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have", "if", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "their", "there", "these", "they", "this", "to", "was", "were", "what", "when", "which", "who", "why", "will", "with", "you", "your"]
)


def _naive_keywords(question: str) -> list[str]:
    """Extract up to 6 distinct lowercase tokens from the question."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in question.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum() or ch == "-")
        if not token or token in _STOP or len(token) < 3:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= 6:
            break
    return tokens
