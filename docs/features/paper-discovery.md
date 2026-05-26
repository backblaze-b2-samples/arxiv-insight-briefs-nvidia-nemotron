<!-- last_verified: 2026-05-26 -->
# Feature: Paper Discovery

## Purpose
Translate a `ResolvedQuery` into a ranked shortlist of arxiv papers via
two steps: an arxiv API metadata query for candidates, then a batched
LLM relevance score against the user's question.

## Used By
- API: `pipeline.py` calls `arxiv_search.find_candidates` and
  `abstract_ranker.rank` between the `searching` and `ranking` stages

## Core Functions
- `app.repo.arxiv_client.search`
- `app.service.arxiv_search.find_candidates`
- `app.service.abstract_ranker.rank`
- `app.service.prompts.ranker.RANKER_SYSTEM` / `build_ranker_user`

## Canonical Files
- `services/api/app/repo/arxiv_client.py`
- `services/api/app/service/arxiv_search.py`
- `services/api/app/service/abstract_ranker.py`
- `services/api/app/service/prompts/ranker.py`

## Inputs
- `ResolvedQuery` from `topic_router`
- `arxiv_candidate_limit` (default 50)
- `brief_paper_limit` (default 8)

## Outputs
- `list[RankedPaper]` (up to 8), each with `relevance_score`, `rank_reason`,
  and arxiv metadata.

## Flow
1. `arxiv_client.search` builds a DSL query:
   `(cat:X OR cat:Y) AND (all:"k1" OR all:"k2") AND submittedDate:[YYYYMMDDHHMM TO ...]`
2. Iterates `arxiv.Client(page_size=50, delay_seconds=3.0).results(search)`
   — the underlying library enforces request spacing.
3. Returns dict rows; `arxiv_search.find_candidates` lifts them into
   `RankedPaper` (no scores yet).
4. `abstract_ranker.rank` builds a single batched prompt with all
   abstracts and asks the LLM for JSON `[{index, score, reason}, ...]`.
5. Scores merge onto the in-memory papers; sort descending; return top-N.

## Fallback path
- LLM unavailable or non-list response → return `papers[:top_k]` in
  arxiv's native recency order. Tests assert this matches the cost
  promise: full text is never spent on papers the ranker rejected.

## Edge Cases
- arxiv returns 0 candidates → caller (`pipeline.py`) sets brief status
  to `done_no_results` and writes a friendly skeleton brief
- LLM scores fewer papers than provided → un-scored papers default to 0
- arxiv API timeout/error → propagates up; pipeline catches and marks
  the brief `failed` with the upstream error in the manifest
- Legacy arxiv ids with slashes/dots → sanitized via `arxiv_client.sanitize_arxiv_id`

## Verification
- Test files: `tests/test_arxiv_search.py`, `tests/test_abstract_ranker.py`
- Required cases: real-shape fixture XML parsing; ranker happy path;
  ranker LLM-unavailable fallback; ranker partial-coverage tolerance
- Quick verify: `pnpm test:api -- tests/test_arxiv_search.py tests/test_abstract_ranker.py`
- Pass criteria: top-N is deterministic given fixed LLM scores; recency
  fallback is order-preserving relative to arxiv response

## Related Docs
- [docs/features/topic-routing.md](topic-routing.md)
- [docs/features/pdf-pipeline.md](pdf-pipeline.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
