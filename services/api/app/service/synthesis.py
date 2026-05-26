"""Insight synthesis — one LLM call that turns N papers into a brief.

Output is markdown with `[arxiv:ID]` citations. The runtime layer rewrites
those citations to presigned PDF links when rendering for the UI.
"""

from __future__ import annotations

import logging

from app.repo import nemotron_client
from app.service.prompts import SYNTHESIS_SYSTEM, build_synthesis_user

logger = logging.getLogger(__name__)


def synthesize(
    question: str,
    paper_blobs: list[tuple[str, str]],
) -> tuple[str | None, dict[str, int]]:
    """Return (markdown, token_usage) or (None, {}) when the LLM is unavailable.

    paper_blobs: list of (arxiv_id, extracted_text). Caller has already
    truncated each text to MAX_PAPER_CHARS.
    """
    if not paper_blobs:
        return None, {}
    try:
        completion = nemotron_client.chat_completion(
            system=SYNTHESIS_SYSTEM,
            user=build_synthesis_user(question, paper_blobs),
            temperature=0.3,
            max_tokens=2200,
        )
    except nemotron_client.NemotronNotConfigured:
        logger.info("synthesis: no NVIDIA key — skipping synthesis stage")
        return None, {}
    except nemotron_client.NemotronError as e:
        logger.warning("synthesis: nemotron error after retries: %s", e)
        return None, {}

    text = nemotron_client.extract_text(completion)
    usage = nemotron_client.extract_usage(completion)
    return (text or None), usage


def build_no_analysis_brief(
    question: str,
    papers: list[tuple[str, str, str]],
) -> str:
    """Skeleton brief used when synthesis is skipped (no NVIDIA key, or all
    papers failed). papers: list of (arxiv_id, title, abstract)."""
    lines = [
        "# Insight brief (no analysis)",
        "",
        f"> **Question:** {question}",
        "",
        (
            "Synthesis was skipped (no `NVIDIA_API_KEY` set, or the upstream "
            "model failed). The arxiv candidates and cached PDFs below are "
            "still archived in B2."
        ),
        "",
        "## Candidate papers",
        "",
    ]
    if not papers:
        lines.append("_No candidate papers were retrieved for this query._")
        return "\n".join(lines)
    for arxiv_id, title, abstract in papers:
        snippet = abstract.strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "..."
        lines.append(f"- **{title}** `[arxiv:{arxiv_id}]`")
        lines.append(f"  {snippet}")
    return "\n".join(lines)


def build_no_results_brief(question: str) -> str:
    """Body used when arxiv returns zero candidates."""
    return (
        "# No recent papers matched\n\n"
        f"> **Question:** {question}\n\n"
        "Try broadening the question, removing very specific jargon, or "
        "widening the time window. The arxiv API returned no results in the "
        "requested categories and window."
    )
