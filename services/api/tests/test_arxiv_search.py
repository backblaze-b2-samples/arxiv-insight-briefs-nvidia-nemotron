"""arxiv_search service tests — wraps the repo client with fakes."""

from datetime import UTC, datetime

from app.service import arxiv_search
from app.types import ResolvedQuery


def _query() -> ResolvedQuery:
    return ResolvedQuery(
        question="q",
        categories=["cs.NI"],
        keywords=["quic"],
        time_window_months=12,
        fallback_used=False,
    )


def test_find_candidates_lifts_dicts_to_models(fake_arxiv):
    fake_arxiv["results"] = [
        {
            "arxiv_id": "2401.12345",
            "raw_arxiv_id": "2401.12345v1",
            "title": "QUIC and BBR",
            "authors": ["A. Researcher"],
            "abstract": "We investigate ...",
            "primary_category": "cs.NI",
            "published": datetime(2024, 1, 5, tzinfo=UTC),
            "pdf_url": "https://arxiv.org/pdf/2401.12345v1",
        }
    ]
    papers = arxiv_search.find_candidates(_query(), max_results=50)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.12345"
    assert papers[0].relevance_score is None  # ranker fills this later


def test_empty_arxiv_returns_empty_list(fake_arxiv):
    fake_arxiv["results"] = []
    assert arxiv_search.find_candidates(_query(), max_results=50) == []
