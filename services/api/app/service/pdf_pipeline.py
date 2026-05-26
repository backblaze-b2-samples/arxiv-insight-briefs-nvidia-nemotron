"""PDF fetch + extraction with B2 content-addressed caching.

The flow per paper:
  1. HEAD `papers/{id}.pdf` — cache hit? skip fetch.
  2. Otherwise HTTPS-fetch from arxiv, PUT to B2.
  3. HEAD `papers/{id}.txt` — extraction cached?
  4. Otherwise PyMuPDF-extract, PUT to B2.
  5. Return the extracted text.

Failures for a single paper are non-fatal — the manifest records the per-paper
status and synthesis runs on whatever survived (one of the design failure modes).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.repo import arxiv_client, b2_client, job_state, pdf_extractor
from app.types import RankedPaper

logger = logging.getLogger(__name__)


@dataclass
class PaperFetchResult:
    arxiv_id: str
    text: str | None
    cached: bool
    status: str  # "ok" | "fetch_failed" | "extract_failed"
    error: str | None = None


def fetch_and_extract(paper: RankedPaper) -> PaperFetchResult:
    """Idempotent: cache hits skip the network + the CPU work entirely."""
    pdf_key = job_state.paper_pdf_key(paper.arxiv_id)
    txt_key = job_state.paper_text_key(paper.arxiv_id)

    # 1 & 2 — PDF cache
    pdf_cached = b2_client.object_exists(pdf_key)
    pdf_bytes: bytes | None = None
    if not pdf_cached:
        try:
            pdf_bytes = arxiv_client.download_pdf(paper.pdf_url)
        except Exception as e:
            logger.warning("pdf_pipeline: fetch failed for %s: %s", paper.arxiv_id, e)
            return PaperFetchResult(
                arxiv_id=paper.arxiv_id,
                text=None,
                cached=False,
                status="fetch_failed",
                error=str(e)[:200],
            )
        try:
            b2_client.put_bytes(pdf_key, pdf_bytes, content_type="application/pdf")
        except RuntimeError as e:
            # PDF couldn't be cached, but we have the bytes in hand — extract anyway.
            logger.warning("pdf_pipeline: B2 PDF cache write failed for %s: %s", paper.arxiv_id, e)

    # 3 & 4 — extracted text cache
    if b2_client.object_exists(txt_key):
        text = b2_client.get_text(txt_key)
        return PaperFetchResult(
            arxiv_id=paper.arxiv_id,
            text=text,
            cached=pdf_cached,  # PDF cache hit, not necessarily text
            status="ok",
        )

    # No cached text — extract now.
    try:
        source_bytes = pdf_bytes if pdf_bytes is not None else b2_client.get_bytes(pdf_key)
        text = pdf_extractor.extract_section_trimmed_text(
            source_bytes, max_chars=settings.max_paper_chars
        )
    except Exception as e:
        logger.warning("pdf_pipeline: extraction failed for %s: %s", paper.arxiv_id, e)
        return PaperFetchResult(
            arxiv_id=paper.arxiv_id,
            text=None,
            cached=pdf_cached,
            status="extract_failed",
            error=str(e)[:200],
        )

    try:
        b2_client.put_text(txt_key, text, content_type="text/plain; charset=utf-8")
    except RuntimeError as e:
        # Non-fatal: we still have the text in memory for synthesis.
        logger.warning("pdf_pipeline: B2 text cache write failed for %s: %s", paper.arxiv_id, e)

    return PaperFetchResult(
        arxiv_id=paper.arxiv_id,
        text=text,
        cached=pdf_cached,
        status="ok",
    )
