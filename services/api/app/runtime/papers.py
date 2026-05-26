"""Paper presigning route — used by the per-citation 'open PDF' link."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.service import briefings as briefings_svc
from app.types import PresignedLink

router = APIRouter()


@router.get("/papers/{arxiv_id}/presign", response_model=PresignedLink)
async def presign_paper(arxiv_id: str, filename: str | None = None) -> PresignedLink:
    """Return a short-lived GET URL for a cached PDF.

    Returns 404 when the paper has not been processed by any brief yet.
    """
    link = briefings_svc.presign_paper_pdf_if_cached(arxiv_id, filename=filename)
    if link is None:
        raise HTTPException(status_code=404, detail="paper not cached")
    return link
