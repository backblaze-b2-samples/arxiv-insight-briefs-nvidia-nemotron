<!-- last_verified: 2026-05-26 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - `/` — new-brief submit form + recent briefings list
  - `/briefings` — full archive (sourced live from B2 via `ListObjectsV2`)
  - `/briefings/[id]` — polled status card → rendered brief + paper cards
  - `/settings` — upstream status panel (B2, NVIDIA) + theme
  - `/design` — living style guide for the kit's primitives
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API: submit / fetch / list / cancel briefings; presign a cached paper
  - Pipeline orchestrator (router → search → rank → PDFs → synthesis)
  - B2 S3 integration via boto3 (`papers/` cache + `briefs/` archive)
  - NVIDIA Build LLM via OpenAI-compatible REST (httpx)
  - arxiv API via `arxiv` library; PDF text via PyMuPDF
  - Health, structured JSON logging, Prometheus metrics endpoint
- **packages/shared/** — TypeScript type definitions, mirroring Pydantic models

## Backend Layering

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2, arxiv API, NVIDIA HTTP, PyMuPDF)
  |
service/   Business logic — pipeline orchestrator, prompts, ranking
  |
runtime/   FastAPI routes — no business logic, no SDK access
```

### Layering rules

1. Dependencies flow downward only.
2. No backward imports (e.g. service must not import from runtime).
3. `boto3` only allowed inside `app/repo/`.
4. All boundary data uses Pydantic models (no raw dicts across layers).
5. Each file stays under 300 lines.
6. LLM prompt strings live in `app/service/prompts/`, never in runtime/.
7. `httpx` only allowed inside `repo/` (where NVIDIA + arxiv-PDF calls live).
8. `pymupdf` only allowed inside `repo/pdf_extractor.py`.

### Directory layout

```
services/api/
  main.py                       App entry, middleware, router registration
  app/
    types/
      briefings.py              BriefRequest, BriefManifest, RankedPaper, ...
    config/
      settings.py               B2 + NVIDIA + tuning knobs
    repo/
      b2_client.py              boto3 S3 client + helpers (HEAD/PUT/GET/LIST/DELETE/presign)
      arxiv_client.py           arxiv library wrapper + httpx PDF download
      arxiv_taxonomy.py         bundled subject taxonomy for router validation
      nemotron_client.py        NVIDIA Build chat-completions client (tenacity retries)
      pdf_extractor.py          PyMuPDF section-trimmed text extraction
      job_state.py              manifest read/write helpers (atomic per-stage save)
    service/
      topic_router.py           NL question → ResolvedQuery
      arxiv_search.py           ResolvedQuery → candidate RankedPapers
      abstract_ranker.py        batched LLM scoring → top-N
      pdf_pipeline.py           cache-aware fetch + extract per paper
      synthesis.py              final LLM call producing markdown
      pipeline.py               orchestrator (status transitions, semaphore)
      metrics_counters.py       thread-safe pipeline metrics
      briefings.py              read/cancel/clear + citation link rewrite
      prompts/
        router.py
        ranker.py
        synthesis.py
    runtime/
      health.py                 /health
      metrics.py                /metrics + request timing middleware
      briefings.py              POST/GET/DELETE /briefings + /briefings/{id}
      papers.py                 GET /papers/{arxiv_id}/presign
  tests/                        pytest (structural + integration with fakes)
```

## Boundary invariants

- **No external SDK leakage**: `boto3`, `arxiv`, `httpx`, `pymupdf` are all
  confined to `app/repo/`. Service code talks to plain Python helpers
  returning typed Pydantic models or simple dicts.
- **No raw dicts across boundaries**: All data crossing layer boundaries
  uses typed Pydantic models.
- **No mutable globals**: Configuration is read-only after init. The
  inflight semaphore in `pipeline.py` and counters in
  `metrics_counters.py` are the only mutable module state, and both are
  thread-safe.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic.
  Arxiv content is treated as untrusted (see [SECURITY.md](docs/SECURITY.md)).

## Data stores

- **Backblaze B2** — the *only* data store.
  - `papers/{arxiv_id}.pdf` — content-addressed PDF cache, shared across briefs.
  - `papers/{arxiv_id}.txt` — section-trimmed extracted text cache.
  - `briefs/{brief_id}/manifest.json` — schema-versioned brief state.
  - `briefs/{brief_id}/brief.md` — generated insight briefing.
  - `briefs/{brief_id}/query.json` — NL question + LLM-resolved query.
- No relational database, no Redis, no message queue. The bucket IS the archive.

## External services

- **Backblaze B2 (S3-compatible API)** — storage, retrieval, presigned GETs.
- **NVIDIA Build (Nemotron / Mistral / Llama)** — chat completions for
  router, ranker, synthesis. OpenAI-compatible endpoint.
- **arxiv.org** — anonymous HTTPS query + PDF download.

## Trust boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for the full posture.

- **Browser → API** — CORS-restricted, scoped to `GET/POST/DELETE/OPTIONS`.
- **API → B2** — application keys + S3v4 signing.
- **API → NVIDIA** — bearer token over HTTPS.
- **API → arxiv** — anonymous HTTPS.
- **Browser → B2 (presigned GET)** — short-lived signature, never exposes credentials.

## Data flows

- **Submit**: `POST /briefings` → `pipeline.acquire_slot()` → write queued
  manifest to B2 → schedule background task → 202 with `brief_id`.
- **Pipeline** (background): routing → searching → ranking → fetching_pdfs
  → synthesizing → done (manifest written after every stage; cancel
  flag checked between stages).
- **Poll**: `GET /briefings/{id}` reads manifest + markdown from B2,
  rewrites `[arxiv:ID]` citations to presigned PDF links, returns
  manifest + markdown.
- **Archive**: `GET /briefings` → `ListObjectsV2 prefix=briefs/` → load
  each manifest → return summaries sorted by `created_at`.
- **Presign a paper**: `GET /papers/{arxiv_id}/presign` → 404 if the PDF
  isn't cached, else short-lived `GeneratePresignedUrl` response.
- **Cancel / clear**: `DELETE /briefings/{id}?mode={cancel|clear}` flips
  the manifest flag or deletes `briefs/{id}/*`. Never touches `papers/`.

## Observability

- Structured JSON logging on every request with `request_id`.
- Request timing middleware (logs duration per request).
- `/metrics` — Prometheus format: HTTP counters + pipeline counters
  (briefs_total, briefs_in_flight, papers_cache_hits/misses,
  nemotron_tokens_total{stage}, nemotron_errors_total{stage}).
- `/health` — B2 connectivity + NVIDIA-configured flag.

## Canonical files

- Orchestrator: `services/api/app/service/pipeline.py`
- B2 data access: `services/api/app/repo/b2_client.py`
- NVIDIA client: `services/api/app/repo/nemotron_client.py`
- arxiv client: `services/api/app/repo/arxiv_client.py`
- PDF extraction: `services/api/app/repo/pdf_extractor.py`
- Prompts: `services/api/app/service/prompts/*.py`
- Pydantic models: `services/api/app/types/briefings.py`
- Settings: `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TS types: `packages/shared/src/types.ts`

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
