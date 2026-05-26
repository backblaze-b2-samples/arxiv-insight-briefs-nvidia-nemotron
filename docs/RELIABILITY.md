<!-- last_verified: 2026-05-26 -->
# Reliability

Reliability expectations for the arxiv-insight-briefs sample.

## Concurrency control

- `MAX_BRIEFS_IN_FLIGHT` (default 2) bounds how many briefings can run
  concurrently. The submit route 503s when saturated rather than queueing
  background work indefinitely.
- Each brief runs in a single FastAPI background task — no thread pool,
  no celery, no external worker. Sufficient for a single-user sample.

## State durability

- Every pipeline stage writes the updated manifest back to B2
  (`briefs/{id}/manifest.json`). If the API restarts mid-pipeline, the
  manifest reflects the last completed stage and the brief shows as
  `routing` / `ranking` / etc. forever — the pipeline does **not**
  auto-resume on restart. Resumption is documented as a follow-up.
- `briefs/{id}/query.json` is written after the router resolves the
  question, so the original NL question + LLM-resolved categories are
  always recoverable.

## Partial success

PDF fetch and extraction can fail per paper without failing the brief:

- A failed paper records `extraction_status` (`fetch_failed` or
  `extract_failed`) and an `extraction_error` string on its `RankedPaper`
  entry in the manifest.
- Synthesis runs against whatever papers succeeded. The brief surfaces
  an "N of M papers" annotation in the markdown header when this happens.
- If **all** papers fail extraction, synthesis is skipped and the brief
  status becomes `done_no_analysis` with a candidate-list skeleton body.

## LLM degradation

- `tenacity` retries `NemotronError` and transport failures up to 3 times
  with exponential backoff inside `app/repo/nemotron_client.py`.
- After retries the service layer catches the failure and produces a
  permissive fallback:
  - Router fails → keyword search over `cs.*` (`fallback_used=True` on the
    manifest's resolved query).
  - Ranker fails → top-N by recency.
  - Synthesis fails → `done_no_analysis` skeleton brief.
- If `NVIDIA_API_KEY` is unset, all three stages take the fallback path
  on the first call (no retries; one log line per stage).

## Cancellation

- `DELETE /briefings/{id}?mode=cancel` flips `cancel_requested` on the
  manifest. The pipeline checks this flag between stages and transitions
  to `cancelled` at the next checkpoint.
- An in-flight HTTP read (arxiv download, NVIDIA call) does not die
  immediately — callers should expect a short delay between requesting
  cancel and seeing the terminal state. Documented in README.

## Cache discipline

- `papers/` cache is content-addressed by sanitized arxiv id. Overlapping
  queries cost zero arxiv re-fetches and zero re-extraction.
- `briefs/` writes are scoped per brief id; clearing one brief never
  touches another or the shared paper cache.
- `delete_prefix` refuses to operate at the bucket root or the sample's
  top-level prefix — defensive guard against accidental data loss.

## Observability

- Structured JSON logging via Python stdlib; every request carries a
  `request_id`.
- `/health` checks B2 reachability and reports `nvidia_configured`.
- `/metrics` (Prometheus text format) exposes:
  - `briefs_total`, `briefs_in_flight`
  - `papers_cache_hits_total`, `papers_cache_misses_total`
  - `nemotron_tokens_total{stage}`
  - `nemotron_errors_total{stage}`
  - HTTP request count and latency per route.

## Known limits

- Single-process in-memory semaphore — does not coordinate across
  replicas. The sample is designed to run as a single API process.
- No background recovery of orphaned `briefs/` (a crash mid-pipeline
  leaves the manifest stuck at the last persisted stage). A janitor
  cron could surface and re-queue these; it is intentionally out of
  scope for v1.
