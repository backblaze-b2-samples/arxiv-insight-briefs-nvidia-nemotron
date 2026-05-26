"""Prometheus-format metrics endpoint + request timing middleware."""

import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.service.metrics_counters import snapshot

logger = logging.getLogger(__name__)

router = APIRouter()

# Thread-safe in-process counters for HTTP request totals.
_lock = Lock()
_request_count: dict[str, int] = defaultdict(int)
_request_duration_sum: dict[str, float] = defaultdict(float)


def record_request(method: str, path: str, status: int, duration: float) -> None:
    key = f"{method}|{path}|{status}"
    with _lock:
        _request_count[key] += 1
        _request_duration_sum[key] += duration


@router.get("/metrics")
async def metrics() -> Response:
    lines: list[str] = []
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    with _lock:
        for key, count in sorted(_request_count.items()):
            parts = key.split("|")
            method, path, status = (parts + ["unknown"] * 3)[:3]
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )
        lines.append("# HELP http_request_duration_seconds Total request duration")
        lines.append("# TYPE http_request_duration_seconds counter")
        for key, duration in sorted(_request_duration_sum.items()):
            parts = key.split("|")
            method, path, status = (parts + ["unknown"] * 3)[:3]
            lines.append(
                f'http_request_duration_seconds{{method="{method}",path="{path}",status="{status}"}} {duration:.6f}'
            )

    # Briefing-pipeline counters live in the service layer.
    snap = snapshot()
    lines.append("# HELP briefs_total Total briefs that have reached a terminal state")
    lines.append("# TYPE briefs_total counter")
    lines.append(f"briefs_total {snap['briefs_total']}")

    lines.append("# HELP briefs_in_flight Briefs currently running")
    lines.append("# TYPE briefs_in_flight gauge")
    lines.append(f"briefs_in_flight {snap['briefs_in_flight']}")

    lines.append("# HELP papers_cache_hits_total Cached PDFs reused")
    lines.append("# TYPE papers_cache_hits_total counter")
    lines.append(f"papers_cache_hits_total {snap['papers_cache_hits_total']}")

    lines.append("# HELP papers_cache_misses_total PDFs fetched fresh from arxiv")
    lines.append("# TYPE papers_cache_misses_total counter")
    lines.append(f"papers_cache_misses_total {snap['papers_cache_misses_total']}")

    lines.append("# HELP nemotron_tokens_total Tokens consumed per pipeline stage")
    lines.append("# TYPE nemotron_tokens_total counter")
    for stage, tokens in sorted(snap["nemotron_tokens"].items()):
        lines.append(f'nemotron_tokens_total{{stage="{stage}"}} {tokens}')

    lines.append("# HELP nemotron_errors_total Upstream failures per pipeline stage")
    lines.append("# TYPE nemotron_errors_total counter")
    for stage, errors in sorted(snap["nemotron_errors"].items()):
        lines.append(f'nemotron_errors_total{{stage="{stage}"}} {errors}')

    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


async def timing_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        logger.error(
            "Unhandled exception: %s %s",
            request.method,
            request.url.path,
            exc_info=True,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    duration = time.time() - start
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    record_request(request.method, path, response.status_code, duration)
    return response
