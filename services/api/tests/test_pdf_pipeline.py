"""pdf_pipeline tests — cache-hit/miss + failure paths."""

from datetime import UTC, datetime

from app.repo import job_state
from app.service import pdf_pipeline
from app.types import RankedPaper


def _paper() -> RankedPaper:
    return RankedPaper(
        arxiv_id="2401.12345",
        title="T",
        authors=["A"],
        abstract="ab",
        primary_category="cs.NI",
        published=datetime(2024, 1, 5, tzinfo=UTC),
        pdf_url="https://arxiv.org/pdf/2401.12345",
    )


def test_cache_miss_writes_pdf_and_text(fake_b2, fake_arxiv, fake_pdf_extractor):
    result = pdf_pipeline.fetch_and_extract(_paper())
    assert result.status == "ok"
    assert result.text and result.text.startswith("Synthetic")
    assert result.cached is False
    # PDF and text both persisted to B2.
    assert f"arxiv-insight-briefs/{job_state.paper_pdf_key('2401.12345')}" in fake_b2
    assert f"arxiv-insight-briefs/{job_state.paper_text_key('2401.12345')}" in fake_b2


def test_pdf_cache_hit_skips_fetch_but_extracts(fake_b2, fake_arxiv, fake_pdf_extractor):
    # Pre-populate the PDF cache so download_pdf is never called.
    fake_b2[f"arxiv-insight-briefs/{job_state.paper_pdf_key('2401.12345')}"] = b"cached-pdf"
    fake_arxiv["pdf_bytes"] = b"SHOULD_NOT_BE_USED"

    result = pdf_pipeline.fetch_and_extract(_paper())
    assert result.status == "ok"
    assert result.cached is True


def test_text_cache_hit_skips_extraction(fake_b2, fake_arxiv, fake_pdf_extractor):
    fake_b2[f"arxiv-insight-briefs/{job_state.paper_pdf_key('2401.12345')}"] = b"pdf"
    fake_b2[f"arxiv-insight-briefs/{job_state.paper_text_key('2401.12345')}"] = b"already-extracted"

    result = pdf_pipeline.fetch_and_extract(_paper())
    assert result.status == "ok"
    assert result.text == "already-extracted"
    assert result.cached is True


def test_fetch_failure_recorded(monkeypatch, fake_b2, fake_pdf_extractor):
    from app.repo import arxiv_client

    def boom(url: str) -> bytes:
        raise RuntimeError("network down")

    monkeypatch.setattr(arxiv_client, "download_pdf", boom)
    result = pdf_pipeline.fetch_and_extract(_paper())
    assert result.status == "fetch_failed"
    assert "network down" in (result.error or "")


def test_extract_failure_recorded(monkeypatch, fake_b2, fake_arxiv):
    from app.repo import pdf_extractor

    def boom(pdf_bytes: bytes, max_chars: int) -> str:
        raise RuntimeError("corrupt pdf")

    monkeypatch.setattr(pdf_extractor, "extract_section_trimmed_text", boom)
    result = pdf_pipeline.fetch_and_extract(_paper())
    assert result.status == "extract_failed"
