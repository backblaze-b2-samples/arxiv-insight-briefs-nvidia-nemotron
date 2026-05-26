"""Service-layer wrapper around the arxiv API.

Returns RankedPaper objects (with relevance_score=None — that's filled by
abstract_ranker downstream). Caller is responsible for hard-capping the
result count via settings.arxiv_candidate_limit.
"""

from __future__ import annotations

import logging

from app.repo import arxiv_client
from app.types import RankedPaper, ResolvedQuery

logger = logging.getLogger(__name__)


def find_candidates(query: ResolvedQuery, max_results: int) -> list[RankedPaper]:
    raw = arxiv_client.search(
        categories=query.categories,
        keywords=query.keywords,
        max_results=max_results,
        time_window_months=query.time_window_months,
    )
    papers: list[RankedPaper] = []
    for item in raw:
        papers.append(
            RankedPaper(
                arxiv_id=item["arxiv_id"],
                title=item["title"],
                authors=item["authors"],
                abstract=item["abstract"],
                primary_category=item["primary_category"],
                published=item["published"],
                pdf_url=item["pdf_url"],
            )
        )
    logger.info(
        "arxiv_search: %d candidates for categories=%s keywords=%s",
        len(papers),
        query.categories,
        query.keywords,
    )
    return papers
