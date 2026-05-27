"""Thin wrapper over the `arxiv` library — never imported outside repo/.

The library uses urllib + a generator API. This module exposes a simpler
list/fetch surface that returns plain dicts so the service layer doesn't
need to know the SDK shape.

Rate-limit handling: arxiv enforces ~1 req / 3s and IP-throttles aggressive
clients for 15-30 min. We layer two defenses:

  * `_client.num_retries=8` — the library's own retry with its 3s delay.
  * A `tenacity` retry on top (4 attempts, exp backoff 30s -> 240s) so the
    pipeline survives transient 429s without surfacing a generic failure.

Anything beyond that budget is a hard IP-level throttle the caller must
wait out; see `service/pipeline.py` for the user-facing surface.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import arxiv
import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class ArxivRateLimitError(RuntimeError):
    """Raised when arxiv's IP-level throttle survives the full retry budget.

    Distinct from a transient `arxiv.HTTPError` so the service/runtime
    layers can branch on it without importing the `arxiv` SDK (keeping
    third-party SDK types pinned to the repo layer).
    """


# Bumped from 3 -> 8: arxiv-py's internal retry uses the same 3s spacing it
# enforces between normal calls, so the extra attempts are cheap and absorb
# brief 429 bursts before our outer tenacity wrap kicks in.
_client = arxiv.Client(page_size=50, delay_seconds=3.0, num_retries=8)


# Legacy arxiv ids contain slashes ("hep-ph/0501012") and modern ones contain dots
# ("2401.12345v1"). Sanitize to a single safe key format for B2.
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_arxiv_id(raw: str) -> str:
    """Normalize an arxiv id to a B2-safe object key segment."""
    return _SAFE_ID_RE.sub("_", raw.strip())


# Outer retry: 30s -> 60s -> 120s -> 240s. `reraise=True` lets the original
# arxiv exception escape so `search()` below can translate it into our
# layer-friendly `ArxivRateLimitError`.
@retry(
    retry=retry_if_exception_type((arxiv.HTTPError, arxiv.UnexpectedEmptyPageError)),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(4),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def _search_with_retry(search_obj: arxiv.Search) -> list[dict[str, Any]]:
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

    Raises `ArxivRateLimitError` if arxiv keeps returning 429 after the
    full retry budget — the service layer maps this onto the
    `failed_arxiv_rate_limit` brief status.
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
    try:
        return _search_with_retry(search_obj)
    except (arxiv.HTTPError, arxiv.UnexpectedEmptyPageError) as e:
        raise ArxivRateLimitError(str(e)) from e


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
    end = datetime.now(UTC)
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


def _is_429(exc: BaseException) -> bool:
    """True for httpx HTTPStatusError on a 429 response."""
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response is not None
        and exc.response.status_code == 429
    )


@retry(
    retry=retry_if_exception(_is_429),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(4),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def download_pdf(pdf_url: str) -> bytes:
    """Fetch a PDF over HTTPS. Intentionally synchronous; the pipeline runs
    inside a background task and arxiv enforces request spacing via the client.

    PDF endpoints throttle independently of the search API — same exponential
    backoff applies for 429s.
    """
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(pdf_url)
        response.raise_for_status()
        return response.content
