"""Orchestrator — moves a brief through router -> search -> rank -> pdfs -> synthesis.

Single entrypoint `run_brief(brief_id, request)`. Designed to be invoked from a
background task; cooperative cancellation is checked between stages via the
manifest's `cancel_requested` flag.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from threading import BoundedSemaphore

from app.config import settings
from app.repo import job_state
from app.service import (
    abstract_ranker,
    arxiv_search,
    pdf_pipeline,
    synthesis,
    topic_router,
)
from app.service.metrics_counters import (
    record_brief_complete,
    record_brief_start,
    record_cache_hit,
    record_cache_miss,
    record_nemotron_tokens,
)
from app.types import BriefManifest, BriefRequest, BriefStatus

logger = logging.getLogger(__name__)

# Soft cap on concurrent briefings — a semaphore so the runtime layer can
# 503 if the queue is full rather than silently piling up background work.
_inflight = BoundedSemaphore(value=settings.max_briefs_in_flight)


class PipelineBusy(RuntimeError):
    """Raised when MAX_BRIEFS_IN_FLIGHT is saturated."""


def acquire_slot() -> bool:
    """Non-blocking semaphore acquire. Callers must release on completion."""
    return _inflight.acquire(blocking=False)


def release_slot() -> None:
    try:
        _inflight.release()
    except ValueError:
        # Defensive — released more than acquired. Shouldn't happen but
        # don't let it crash a background task.
        logger.warning("pipeline: semaphore release with no acquire")


def new_brief_id() -> str:
    return uuid.uuid4().hex


def create_pending_brief(request: BriefRequest) -> str:
    """Create + persist a queued manifest, return the brief id.

    Done synchronously so the API can hand back an id the moment the background
    task is scheduled.
    """
    brief_id = new_brief_id()
    manifest = initial_manifest(brief_id, request)
    job_state.save_manifest(manifest)
    return brief_id


def initial_manifest(brief_id: str, request: BriefRequest) -> BriefManifest:
    """Persisted before the background task starts so /briefings/{id} returns 200 immediately."""
    now = datetime.now(UTC)
    return BriefManifest(
        brief_id=brief_id,
        status="queued",
        created_at=now,
        updated_at=now,
        question=request.question,
        resolved_query=_blank_resolved(request),
    )


def _blank_resolved(request: BriefRequest):
    from app.types import ResolvedQuery

    return ResolvedQuery(
        question=request.question,
        categories=[],
        keywords=[],
        time_window_months=request.time_window_months
        or settings.brief_time_window_months,
        fallback_used=False,
    )


def _check_cancel(manifest: BriefManifest) -> bool:
    fresh = job_state.load_manifest(manifest.brief_id)
    if fresh and fresh.cancel_requested:
        manifest.status = "cancelled"
        job_state.save_manifest(manifest)
        return True
    return False


def _set_status(manifest: BriefManifest, status: BriefStatus) -> None:
    manifest.status = status
    job_state.save_manifest(manifest)


def run_brief(brief_id: str, request: BriefRequest) -> None:
    """Main pipeline. Catches and records terminal failures in the manifest."""
    record_brief_start()
    try:
        manifest = job_state.load_manifest(brief_id)
        if manifest is None:
            manifest = initial_manifest(brief_id, request)
            job_state.save_manifest(manifest)
        _run_inner(manifest, request)
    except Exception as e:
        logger.exception("pipeline: unhandled error for brief %s", brief_id)
        manifest = job_state.load_manifest(brief_id)
        if manifest is not None:
            manifest.status = "failed"
            manifest.error = str(e)[:500]
            job_state.save_manifest(manifest)
    finally:
        record_brief_complete()
        release_slot()


def _run_inner(manifest: BriefManifest, request: BriefRequest) -> None:
    # --- Stage 1: route ---
    _set_status(manifest, "routing")
    resolved = topic_router.resolve_query(request.question, request.time_window_months)
    manifest.resolved_query = resolved
    job_state.save_query(
        manifest.brief_id,
        {
            "question": request.question,
            "resolved": resolved.model_dump(mode="json"),
        },
    )
    job_state.save_manifest(manifest)
    if _check_cancel(manifest):
        return

    # --- Stage 2: search ---
    _set_status(manifest, "searching")
    candidates = arxiv_search.find_candidates(resolved, settings.arxiv_candidate_limit)
    if not candidates:
        manifest.ranked_papers = []
        body = synthesis.build_no_results_brief(request.question)
        manifest.brief_markdown_key = job_state.save_brief_markdown(manifest.brief_id, body)
        _set_status(manifest, "done_no_results")
        return
    if _check_cancel(manifest):
        return

    # --- Stage 3: rank ---
    _set_status(manifest, "ranking")
    top_papers = abstract_ranker.rank(
        request.question, candidates, settings.brief_paper_limit
    )
    manifest.ranked_papers = top_papers
    job_state.save_manifest(manifest)
    if _check_cancel(manifest):
        return

    # --- Stage 4: PDFs ---
    _set_status(manifest, "fetching_pdfs")
    paper_blobs: list[tuple[str, str]] = []
    for paper in manifest.ranked_papers:
        result = pdf_pipeline.fetch_and_extract(paper)
        paper.cached = result.cached
        paper.extraction_status = result.status if result.status != "ok" else "ok"
        paper.extraction_error = result.error
        if result.cached:
            manifest.papers_cache_hits += 1
            record_cache_hit()
        else:
            manifest.papers_cache_misses += 1
            record_cache_miss()
        if result.status == "ok" and result.text:
            paper_blobs.append((paper.arxiv_id, result.text))
        if _check_cancel(manifest):
            return
    job_state.save_manifest(manifest)

    # --- Stage 5: synthesis ---
    _set_status(manifest, "synthesizing")
    body, usage = synthesis.synthesize(request.question, paper_blobs)
    if usage:
        manifest.nemotron_tokens["synthesis"] = usage.get("total_tokens", 0)
        record_nemotron_tokens("synthesis", usage.get("total_tokens", 0))

    if body is None:
        # Synthesis was skipped (no key or upstream failure). Still produce
        # a brief that lists the candidates so B2 archive is non-empty.
        body = synthesis.build_no_analysis_brief(
            request.question,
            [(p.arxiv_id, p.title, p.abstract) for p in manifest.ranked_papers],
        )
        manifest.brief_markdown_key = job_state.save_brief_markdown(manifest.brief_id, body)
        _set_status(manifest, "done_no_analysis")
        return

    manifest.brief_markdown_key = job_state.save_brief_markdown(manifest.brief_id, body)
    _set_status(manifest, "done")
