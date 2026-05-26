<!-- last_verified: 2026-05-26 -->
# Feature: Topic Routing

## Purpose
Convert a natural-language research question into a structured arxiv
search plan (categories + keywords + time window) using a single Nemotron
call, with a deterministic fallback when the LLM is unavailable.

## Used By
- UI: `/` (New brief form) feeds the user's question through this stage
- API: invoked as the first pipeline stage in `app/service/pipeline.py`

## Core Functions
- `app.service.topic_router.resolve_query(question, override_window)`
- `app.repo.arxiv_taxonomy.filter_valid(codes)`
- `app.service.prompts.router.ROUTER_SYSTEM` / `build_router_user`

## Canonical Files
- `services/api/app/service/topic_router.py`
- `services/api/app/service/prompts/router.py`
- `services/api/app/repo/arxiv_taxonomy.py`

## Inputs
- question: `str` — user-supplied, 4-500 chars (boundary-validated by `BriefRequest`)
- override_window: `int | None` — optional override of the default time window

## Outputs
- `ResolvedQuery` Pydantic model with:
  - `categories: list[str]` (validated against bundled taxonomy)
  - `keywords: list[str]` (up to 6, deduped)
  - `time_window_months: int` (1–120, clamped)
  - `fallback_used: bool`
  - `warnings: list[str]` (e.g. "dropped invalid categories: cs.AGI")

## Flow
1. Call `nemotron_client.chat_completion` with the router system prompt
   and the question wrapped in `<question>` tags.
2. Parse the JSON response (tolerant — strips ```json fences).
3. Filter `categories` against `arxiv_taxonomy.ARXIV_CATEGORIES`; dropped
   codes become a warning.
4. If all categories were invalid, default to `["cs"]` (cs.* prefix).
5. Clamp `time_window_months` to [1, 120].
6. Return `ResolvedQuery`.

## Fallback path
Triggered by `NemotronNotConfigured`, `NemotronError` after retries, or a
non-JSON response:
- `categories = ["cs"]`
- `keywords` = naive tokenization of the question (lowercase, stopword
  removal, dedup, ≤6 tokens)
- `fallback_used = True`
- One warning explaining which condition triggered fallback.

## Edge Cases
- LLM returns no categories → defaulted to `["cs"]` with a warning
- LLM returns mostly invalid codes (e.g. `cs.AGI`) → dropped, warning recorded
- LLM returns time_window outside [1, 120] → clamped
- Question is empty after stopword removal → keyword list may be empty;
  the search step then runs as a pure category sweep
- NVIDIA rate-limited or 5xx after retries → fallback path, no exception

## Verification
- Test file: `services/api/tests/test_topic_router.py`
- Required cases: valid LLM response; LLM hallucinated category dropped;
  all-invalid categories fall through to `cs`; `NemotronNotConfigured`
  fallback; non-JSON response fallback
- Quick verify: `pnpm test:api -- tests/test_topic_router.py`
- Pass criteria: every branch above returns a valid `ResolvedQuery`,
  never raises

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/SECURITY.md](../SECURITY.md) — prompt-injection envelope
