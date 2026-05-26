"""Briefing HTTP routes — submit, fetch, list, cancel, clear.

Layer rule: no boto3, no LLM calls here. This module only calls into
`app.service` and translates results into HTTP responses.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.service import briefings as briefings_svc
from app.service import pipeline
from app.types import BriefManifest, BriefRequest, BriefSummary

logger = logging.getLogger(__name__)

router = APIRouter()


class BriefSubmitResponse(BaseModel):
    brief_id: str
    status: str


class BriefDetail(BaseModel):
    """Brief manifest + rendered markdown (server-side citation rewrite)."""

    manifest: BriefManifest
    markdown: str | None = None


@router.post("/briefings", response_model=BriefSubmitResponse, status_code=202)
async def submit_briefing(
    payload: BriefRequest, background_tasks: BackgroundTasks
) -> BriefSubmitResponse:
    """Create a new brief and kick off the pipeline in the background.

    Returns 202 immediately with the brief id; clients poll `/briefings/{id}`.
    """
    if not pipeline.acquire_slot():
        raise HTTPException(
            status_code=503,
            detail="Too many briefings in flight. Try again in a minute.",
        )
    brief_id = pipeline.create_pending_brief(payload)
    background_tasks.add_task(pipeline.run_brief, brief_id, payload)
    return BriefSubmitResponse(brief_id=brief_id, status="queued")


@router.get("/briefings", response_model=list[BriefSummary])
async def list_briefings(limit: int = 100) -> list[BriefSummary]:
    return briefings_svc.list_briefs(limit=min(limit, 500))


@router.get("/briefings/{brief_id}", response_model=BriefDetail)
async def get_briefing(brief_id: str) -> BriefDetail:
    manifest = briefings_svc.get_manifest(brief_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="brief not found")
    briefings_svc.attach_citations(manifest)
    markdown = briefings_svc.get_brief_markdown(brief_id)
    if markdown is not None:
        markdown = briefings_svc.render_citations_to_links(markdown, manifest)
    return BriefDetail(manifest=manifest, markdown=markdown)


@router.delete("/briefings/{brief_id}", status_code=204)
async def cancel_or_clear_briefing(brief_id: str, mode: str = "cancel") -> None:
    """`mode=cancel` flags for cooperative cancel; `mode=clear` deletes B2 artifacts.

    Clearing never touches `papers/` — the shared PDF cache is preserved.
    """
    if mode == "cancel":
        if not briefings_svc.cancel_brief(brief_id):
            raise HTTPException(status_code=404, detail="brief not found")
        return None
    if mode == "clear":
        if not briefings_svc.clear_brief(brief_id):
            raise HTTPException(status_code=404, detail="brief not found")
        return None
    raise HTTPException(status_code=400, detail="mode must be 'cancel' or 'clear'")
