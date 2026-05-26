"""Thread-safe counters surfaced on /metrics.

Lives in the service layer because the orchestrator owns the events. The
runtime/metrics.py endpoint reads these read-only.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

_lock = Lock()
_briefs_total = 0
_briefs_in_flight = 0
_papers_cache_hits = 0
_papers_cache_misses = 0
_nemotron_tokens: dict[str, int] = defaultdict(int)
_nemotron_errors: dict[str, int] = defaultdict(int)


def record_brief_start() -> None:
    global _briefs_in_flight
    with _lock:
        _briefs_in_flight += 1


def record_brief_complete() -> None:
    global _briefs_total, _briefs_in_flight
    with _lock:
        _briefs_total += 1
        _briefs_in_flight = max(0, _briefs_in_flight - 1)


def record_cache_hit() -> None:
    global _papers_cache_hits
    with _lock:
        _papers_cache_hits += 1


def record_cache_miss() -> None:
    global _papers_cache_misses
    with _lock:
        _papers_cache_misses += 1


def record_nemotron_tokens(stage: str, tokens: int) -> None:
    with _lock:
        _nemotron_tokens[stage] += tokens


def record_nemotron_error(stage: str) -> None:
    with _lock:
        _nemotron_errors[stage] += 1


def snapshot() -> dict:
    with _lock:
        return {
            "briefs_total": _briefs_total,
            "briefs_in_flight": _briefs_in_flight,
            "papers_cache_hits_total": _papers_cache_hits,
            "papers_cache_misses_total": _papers_cache_misses,
            "nemotron_tokens": dict(_nemotron_tokens),
            "nemotron_errors": dict(_nemotron_errors),
        }
