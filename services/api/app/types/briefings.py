"""Brief request, status, and manifest models — boundary types."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Lifecycle states for a brief. Use plain string literals (not Enum) so the
# values round-trip cleanly through JSON and match the TS mirror in
# packages/shared/src/types.ts.
BriefStatus = Literal[
    "queued",
    "routing",
    "searching",
    "ranking",
    "fetching_pdfs",
    "synthesizing",
    "done",
    "done_no_results",
    "done_no_analysis",
    "failed",
    "failed_llm",
    # arxiv's IP-level throttle is outside our retry budget — surfaced as a
    # distinct, user-actionable state ("wait 15-30 min") rather than a
    # generic failure.
    "failed_arxiv_rate_limit",
    "cancelled",
]


class BriefRequest(BaseModel):
    """The user's natural-language brief request."""

    question: str = Field(min_length=4, max_length=500)
    # Optional override of the default time window (months). None = use setting.
    time_window_months: int | None = Field(default=None, ge=1, le=120)


class ResolvedQuery(BaseModel):
    """LLM-resolved structured query, persisted as briefs/{id}/query.json."""

    question: str
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    time_window_months: int
    # True when the router was skipped (no NVIDIA_API_KEY or LLM failure).
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)


class RankedPaper(BaseModel):
    """One arxiv paper after metadata fetch + abstract rank.

    Lives both in the manifest and in the API response. The `cached` flag
    distinguishes B2 cache hits from fresh fetches for the UI "cached" badge.
    """

    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    primary_category: str
    published: datetime
    pdf_url: str
    relevance_score: float | None = None
    rank_reason: str | None = None
    # Set after pdf_pipeline runs.
    cached: bool = False
    extraction_status: Literal["pending", "ok", "fetch_failed", "extract_failed"] = "pending"
    extraction_error: str | None = None


class Citation(BaseModel):
    """A claim's source arxiv id(s). Rendered as clickable presigned links."""

    arxiv_id: str
    presigned_url: str | None = None


class InsightSection(BaseModel):
    """One bullet inside a brief section, with citations."""

    text: str
    citations: list[Citation] = Field(default_factory=list)


class BriefManifest(BaseModel):
    """Schema-versioned record of one brief — written as briefs/{id}/manifest.json."""

    schema_version: int = 1
    brief_id: str
    status: BriefStatus
    created_at: datetime
    updated_at: datetime
    question: str
    resolved_query: ResolvedQuery
    ranked_papers: list[RankedPaper] = Field(default_factory=list)
    # Filled when status == "done" (or done_no_analysis with skeleton content).
    brief_markdown_key: str | None = None
    # Aggregated counters surfaced on /metrics and the brief detail page.
    papers_cache_hits: int = 0
    papers_cache_misses: int = 0
    nemotron_tokens: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    cancel_requested: bool = False


class BriefSummary(BaseModel):
    """List-page item — small subset of the manifest."""

    brief_id: str
    question: str
    status: BriefStatus
    created_at: datetime
    paper_count: int


class PresignedLink(BaseModel):
    """Presigned GET URL for a cached PDF or brief markdown file."""

    key: str
    url: str
    expires_in: int
