"""Thin wrapper over the `arxiv` library — never imported outside repo/.

The library uses urllib + a generator API. This module exposes a simpler
list/fetch surface that returns plain dicts so the service layer doesn't
need to know the SDK shape.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import arxiv

# Public clients are reused across calls; arxiv-py recommends one per process.
_client = arxiv.Client(page_size=50, delay_seconds=3.0, num_retries=3)


# Legacy arxiv ids contain slashes ("hep-ph/0501012") and modern ones contain dots
# ("2401.12345v1"). Sanitize to a single safe key format for B2.
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_arxiv_id(raw: str) -> str:
    """Normalize an arxiv id to a B2-safe object key segment."""
    return _SAFE_ID_RE.sub("_", raw.strip())


def search(
    categories: list[str],
    keywords: list[str],
    max_results: int,
    time_window_months: int,
) -> list[dict[str, Any]]:
    """Run an arxiv API query and return paper metadata.

    Filters by submission date (`submittedDate`) so the result set is
    bounded by `time_window_months`. Categories and keywords are AND-ed
    together — keywords inside the bundle are OR-ed via parens.
    """
    query = _build_query(categories, keywords, time_window_months)
    if not query:
        return []
    search_obj = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    results: list[dict[str, Any]] = []
    for paper in _client.results(search_obj):
        results.append(
            {
                "arxiv_id": sanitize_arxiv_id(paper.get_short_id()),
                "raw_arxiv_id": paper.get_short_id(),
                "title": paper.title.strip(),
                "authors": [a.name for a in paper.authors],
                "abstract": paper.summary.strip(),
                "primary_category": paper.primary_category,
                "published": paper.published,
                "pdf_url": paper.pdf_url,
            }
        )
    return results


def _build_query(categories: list[str], keywords: list[str], months: int) -> str:
    """Compose an arxiv search query string.

    arxiv's query DSL: cat:cs.NI AND (all:"quic" OR all:"bbr")
    AND submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]
    """
    parts: list[str] = []
    if categories:
        cat_clause = " OR ".join(f"cat:{c}" for c in categories)
        parts.append(f"({cat_clause})")
    if keywords:
        kw_clause = " OR ".join(f'all:"{kw}"' for kw in keywords if kw.strip())
        if kw_clause:
            parts.append(f"({kw_clause})")
    if not parts:
        return ""
    # Time window. Use the YYYYMMDDHHMM format the arxiv API expects.
    end = datetime.utcnow()
    # Approximate "N months ago" as N * 30 days — close enough for a research feed.
    start_year = end.year
    start_month = end.month - months
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = end.replace(year=start_year, month=start_month, day=1)
    fmt = "%Y%m%d%H%M"
    parts.append(f"submittedDate:[{start.strftime(fmt)} TO {end.strftime(fmt)}]")
    return " AND ".join(parts)


def download_pdf(pdf_url: str) -> bytes:
    """Fetch a PDF over HTTPS. Intentionally synchronous; the pipeline runs
    inside a background task and arxiv enforces request spacing via the client.
    """
    import httpx

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(pdf_url)
        response.raise_for_status()
        return response.content
