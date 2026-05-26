"""abstract_ranker tests — batched scoring + LLM fallback to recency."""

import json
from datetime import UTC, datetime

from app.service import abstract_ranker
from app.types import RankedPaper


def _paper(i: int, score_hint: str = "") -> RankedPaper:
    return RankedPaper(
        arxiv_id=f"240{i}.0000{i}",
        title=f"Paper {i} {score_hint}",
        authors=["A"],
        abstract=f"Abstract for paper {i}. {score_hint}",
        primary_category="cs.NI",
        published=datetime(2024, 1, i + 1, tzinfo=UTC),
        pdf_url=f"https://arxiv.org/pdf/240{i}.0000{i}",
    )


def test_rank_orders_by_llm_score(fake_nemotron):
    papers = [_paper(i) for i in range(5)]
    fake_nemotron["responses"].append(
        json.dumps(
            [
                {"index": 0, "score": 1.0, "reason": "low"},
                {"index": 1, "score": 9.0, "reason": "highest"},
                {"index": 2, "score": 5.0, "reason": "mid"},
                {"index": 3, "score": 8.0, "reason": "second"},
                {"index": 4, "score": 2.0, "reason": "low"},
            ]
        )
    )
    top = abstract_ranker.rank("q", papers, top_k=3)
    assert [p.arxiv_id for p in top] == [papers[1].arxiv_id, papers[3].arxiv_id, papers[2].arxiv_id]
    assert top[0].rank_reason == "highest"


def test_rank_falls_back_to_recency_when_llm_missing(fake_nemotron):
    fake_nemotron["configured"] = False
    papers = [_paper(i) for i in range(5)]
    top = abstract_ranker.rank("q", papers, top_k=2)
    # Recency order = arxiv's native order = input order.
    assert [p.arxiv_id for p in top] == [papers[0].arxiv_id, papers[1].arxiv_id]


def test_rank_tolerates_partial_coverage(fake_nemotron):
    papers = [_paper(i) for i in range(3)]
    fake_nemotron["responses"].append(
        json.dumps([{"index": 1, "score": 5.0, "reason": "ok"}])
    )
    top = abstract_ranker.rank("q", papers, top_k=2)
    # Unscored papers default to 0, so the scored one comes first.
    assert top[0].arxiv_id == papers[1].arxiv_id


def test_rank_short_circuits_when_top_k_exceeds_input(fake_nemotron):
    papers = [_paper(i) for i in range(2)]
    # Should not call the LLM at all.
    top = abstract_ranker.rank("q", papers, top_k=5)
    assert top == papers
    assert fake_nemotron["calls"] == []
