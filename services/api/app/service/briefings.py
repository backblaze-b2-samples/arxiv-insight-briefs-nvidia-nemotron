"""Briefing lifecycle helpers — list, get, cancel, clear.

The pipeline orchestrator lives in `pipeline.py`; this module holds the read
side and admin operations the runtime/ routers call.
"""

from __future__ import annotations

import re

from app.config import settings
from app.repo import b2_client, job_state
from app.types import BriefManifest, BriefSummary, Citation, PresignedLink, RankedPaper


def get_manifest(brief_id: str) -> BriefManifest | None:
    return job_state.load_manifest(brief_id)


def list_briefs(limit: int = 100) -> list[BriefSummary]:
    """Return all briefs (newest first), sourced from `briefs/*/manifest.json` in B2."""
    items = b2_client.list_prefix("briefs/", max_keys=limit * 10)
    summaries: list[BriefSummary] = []
    for item in items:
        key = item["key"]
        if not key.endswith("/manifest.json"):
            continue
        # `briefs/{id}/manifest.json` -> id
        parts = key.split("/")
        if len(parts) != 3:
            continue
        brief_id = parts[1]
        manifest = job_state.load_manifest(brief_id)
        if manifest is None:
            continue
        summaries.append(
            BriefSummary(
                brief_id=brief_id,
                question=manifest.question,
                status=manifest.status,
                created_at=manifest.created_at,
                paper_count=len(manifest.ranked_papers),
            )
        )
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries[:limit]


def cancel_brief(brief_id: str) -> bool:
    """Mark the brief for cooperative cancellation.

    Returns True if the manifest existed (whether or not it was still in-flight).
    The pipeline checks `cancel_requested` between stages — an in-flight network
    read won't die immediately.
    """
    manifest = job_state.load_manifest(brief_id)
    if manifest is None:
        return False
    if manifest.status not in {"done", "done_no_results", "done_no_analysis", "failed", "cancelled"}:
        manifest.cancel_requested = True
        job_state.save_manifest(manifest)
    return True


def clear_brief(brief_id: str) -> bool:
    """Delete all artifacts for a single brief. Never touches papers/ cache."""
    deleted = b2_client.delete_prefix(f"briefs/{brief_id}/")
    return deleted > 0


def clear_all_briefs() -> int:
    """Delete every object under the `briefs/` prefix.

    Returns the count of objects removed. The shared `papers/` PDF cache is
    explicitly preserved — that's the whole point of the danger-zone action.
    The hard floor against bucket-root deletion lives in
    `b2_client.delete_prefix`.
    """
    return b2_client.delete_prefix("briefs/")


def get_brief_markdown(brief_id: str) -> str | None:
    """Read the brief markdown body from B2."""
    key = job_state.brief_markdown_key(brief_id)
    if not b2_client.object_exists(key):
        return None
    return b2_client.get_text(key)


_CITATION_RE = re.compile(r"\[arxiv:([A-Za-z0-9._-]+)\]")


def render_citations_to_links(markdown: str, brief: BriefManifest) -> str:
    """Rewrite `[arxiv:ID]` placeholders to short-lived presigned PDF links.

    Done server-side so the markdown shipped to the UI is plain Markdown +
    HTTPS links — the browser doesn't need to know how presigning works.
    """
    arxiv_ids = {p.arxiv_id for p in brief.ranked_papers}

    def replace(match: re.Match) -> str:
        arxiv_id = match.group(1)
        if arxiv_id not in arxiv_ids:
            return match.group(0)  # unknown citation — leave it
        try:
            url = b2_client.presign_get(job_state.paper_pdf_key(arxiv_id))
        except RuntimeError:
            return match.group(0)
        return f"[arxiv:{arxiv_id}]({url})"

    return _CITATION_RE.sub(replace, markdown)


def presign_paper_pdf(arxiv_id: str, filename: str | None = None) -> PresignedLink:
    """Generate a short-lived link to a cached paper PDF."""
    key = job_state.paper_pdf_key(arxiv_id)
    url = b2_client.presign_get(key, filename=filename)
    return PresignedLink(key=key, url=url, expires_in=settings.presigned_ttl_seconds)


def presign_paper_pdf_if_cached(
    arxiv_id: str, filename: str | None = None
) -> PresignedLink | None:
    """Same as `presign_paper_pdf` but returns None if the PDF isn't cached."""
    key = job_state.paper_pdf_key(arxiv_id)
    if not b2_client.object_exists(key):
        return None
    return presign_paper_pdf(arxiv_id, filename=filename)


def attach_citations(brief: BriefManifest) -> list[RankedPaper]:
    """Annotate ranked papers with presigned PDF URLs for the UI.

    Mutates the in-memory copy only — the manifest in B2 stays free of
    short-lived URLs.
    """
    for paper in brief.ranked_papers:
        if paper.extraction_status in {"ok", "pending"}:
            try:
                paper_pdf = b2_client.presign_get(
                    job_state.paper_pdf_key(paper.arxiv_id)
                )
                paper.pdf_url = paper_pdf  # overlay with presigned for UI
            except RuntimeError:
                # leave the original arxiv URL in place if presign fails
                pass
    return brief.ranked_papers


__all__ = [
    "Citation",
    "attach_citations",
    "cancel_brief",
    "clear_all_briefs",
    "clear_brief",
    "get_brief_markdown",
    "get_manifest",
    "list_briefs",
    "presign_paper_pdf",
    "render_citations_to_links",
]
