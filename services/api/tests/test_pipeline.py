"""End-to-end pipeline test with all upstream surfaces faked."""

import json
from datetime import UTC, datetime

import pytest

from app.repo import job_state
from app.service import pipeline
from app.types import BriefRequest


@pytest.fixture
def fake_results():
    return [
        {
            "arxiv_id": "2401.12345",
            "raw_arxiv_id": "2401.12345v1",
            "title": "QUIC and BBR",
            "authors": ["A. Researcher"],
            "abstract": "We investigate ...",
            "primary_category": "cs.NI",
            "published": datetime(2024, 1, 5, tzinfo=UTC),
            "pdf_url": "https://arxiv.org/pdf/2401.12345v1",
        },
        {
            "arxiv_id": "2403.55555",
            "raw_arxiv_id": "2403.55555",
            "title": "Striping",
            "authors": ["B. Researcher"],
            "abstract": "We benchmark ...",
            "primary_category": "cs.DC",
            "published": datetime(2024, 3, 10, tzinfo=UTC),
            "pdf_url": "https://arxiv.org/pdf/2403.55555",
        },
    ]


def test_happy_path(fake_b2, fake_arxiv, fake_nemotron, fake_pdf_extractor, fake_results):
    fake_arxiv["results"] = fake_results
    fake_nemotron["responses"] = [
        # router
        json.dumps(
            {
                "categories": ["cs.NI"],
                "keywords": ["quic"],
                "time_window_months": 12,
            }
        ),
        # ranker
        json.dumps(
            [
                {"index": 0, "score": 9.0, "reason": "directly answers"},
                {"index": 1, "score": 4.0, "reason": "tangential"},
            ]
        ),
        # synthesis
        "# Key Findings\n- BBR helps [arxiv:2401.12345]\n",
    ]
    request = BriefRequest(question="how do we send files faster?", time_window_months=12)
    brief_id = pipeline.create_pending_brief(request)
    assert pipeline.acquire_slot()
    pipeline.run_brief(brief_id, request)

    manifest = job_state.load_manifest(brief_id)
    assert manifest is not None
    assert manifest.status == "done"
    assert manifest.brief_markdown_key is not None
    assert manifest.papers_cache_hits + manifest.papers_cache_misses == 2
    assert manifest.nemotron_tokens.get("synthesis", 0) > 0


def test_no_results_path(fake_b2, fake_arxiv, fake_nemotron, fake_pdf_extractor):
    fake_arxiv["results"] = []
    fake_nemotron["responses"] = [
        json.dumps(
            {"categories": ["cs.NI"], "keywords": ["foo"], "time_window_months": 12}
        )
    ]
    request = BriefRequest(question="anything")
    brief_id = pipeline.create_pending_brief(request)
    assert pipeline.acquire_slot()
    pipeline.run_brief(brief_id, request)

    manifest = job_state.load_manifest(brief_id)
    assert manifest.status == "done_no_results"
    assert manifest.brief_markdown_key is not None


def test_no_analysis_path(fake_b2, fake_arxiv, fake_nemotron, fake_pdf_extractor, fake_results):
    fake_arxiv["results"] = fake_results
    fake_nemotron["configured"] = False  # router + ranker + synthesis all degrade
    request = BriefRequest(question="anything")
    brief_id = pipeline.create_pending_brief(request)
    assert pipeline.acquire_slot()
    pipeline.run_brief(brief_id, request)

    manifest = job_state.load_manifest(brief_id)
    assert manifest.status == "done_no_analysis"
    assert manifest.resolved_query.fallback_used is True
