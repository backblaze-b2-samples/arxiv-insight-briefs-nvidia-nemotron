"""Batched LLM relevance ranker over abstracts.

This is the cost lever — one batched call ranks ~50 abstracts and we only
spend full-text tokens on the top ~8 survivors. If the LLM is unavailable,
we fall back to recency order (papers come back from arxiv newest-first).
"""

from __future__ import annotations

import logging

from app.repo import nemotron_client
from app.service.prompts import RANKER_SYSTEM, build_ranker_user
from app.types import RankedPaper

logger = logging.getLogger(__name__)


def rank(question: str, papers: list[RankedPaper], top_k: int) -> list[RankedPaper]:
    """Return the top `top_k` papers, scored against the question.

    Mutates `relevance_score` and `rank_reason` on the returned subset.
    """
    if not papers:
        return []
    if top_k >= len(papers):
        return papers

    abstracts = [(i, p.arxiv_id, p.abstract) for i, p in enumerate(papers)]
    try:
        completion = nemotron_client.chat_completion(
            system=RANKER_SYSTEM,
            user=build_ranker_user(question, abstracts),
            temperature=0.1,
            max_tokens=1500,
            response_format_json=True,
        )
    except nemotron_client.NemotronNotConfigured:
        logger.info("abstract_ranker: no NVIDIA key, falling back to recency order")
        return papers[:top_k]
    except nemotron_client.NemotronError as e:
        logger.warning("abstract_ranker: nemotron error after retries: %s", e)
        return papers[:top_k]

    text = nemotron_client.extract_text(completion)
    parsed = nemotron_client.parse_json_or_none(text)
    if not isinstance(parsed, list):
        logger.warning("abstract_ranker: non-list response, falling back to recency")
        return papers[:top_k]

    # Apply scores. Tolerate missing entries — un-scored papers default to 0.
    scored: dict[int, tuple[float, str]] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        try:
            idx = int(entry.get("index"))
            score = float(entry.get("score", 0))
        except (TypeError, ValueError):
            continue
        reason = str(entry.get("reason", "")).strip()[:200]
        scored[idx] = (score, reason)

    ranked = []
    for i, paper in enumerate(papers):
        score, reason = scored.get(i, (0.0, ""))
        paper.relevance_score = score
        paper.rank_reason = reason or None
        ranked.append(paper)

    ranked.sort(key=lambda p: (p.relevance_score or 0.0), reverse=True)
    return ranked[:top_k]
