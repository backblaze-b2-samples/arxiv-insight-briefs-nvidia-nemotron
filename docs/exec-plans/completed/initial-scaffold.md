# Plan — arxiv-insight-briefs

> Scaffold a new B2 sample from `vibe-coding-starter-kit`. User types a natural-language research question (e.g. *"latest research on sending files over the internet"*) → backend uses Mistral Nemotron (free via build.nvidia.com) as a router to pick arxiv categories + keywords → arxiv API returns ~50 candidates → LLM ranks abstracts → top ~8 PDFs are downloaded and cached in B2 (content-addressed) → PyMuPDF extracts section-trimmed text → Nemotron produces a *problem-anchored* insight brief, not a generic summary → brief + manifest archived to B2; presigned links surface the source PDFs.

Plan locked through conversation iteration with the user; sourced from full recon of `vibe-coding-starter-kit` (apps/web, services/api, packages/shared, docs/). Free-tier model availability assumed per user; builder will verify the exact `mistralai/mistral-nemotron` model id on `build.nvidia.com` and fall back to `mistralai/mistral-medium` or `meta/llama-3.3-70b-instruct` if it is gated.

---

## 1. Purpose

`arxiv-insight-briefs` is a reference sample for Backblaze prospects and employees building an *insight-extraction* pipeline whose source-of-truth (PDFs + generated reports) lives in B2. It targets a real workflow: a researcher, founder, or PM asks "what's the state of X in arxiv right now, and what should I actually take away from it?" — and gets back a structured brief with cited links, not a list of search results.

The sample demonstrates three distinct B2 patterns in one app:

1. **Content-addressed cache** — papers stored under `papers/{arxiv_id}.pdf`, shared across every brief. Overlapping queries cost zero arxiv re-fetches and zero re-extraction.
2. **Durable artifact archive** — every brief saved as `briefs/{brief_id}/brief.md` + `manifest.json`, browsable as a "past briefings" feed in the UI.
3. **Presigned-URL fan-out** — each citation in a brief resolves to a short-lived presigned GET against the cached PDF, so the brief itself is sharable without leaking credentials.

It also demonstrates a deliberately *least-resource-intensive* AI design: no embeddings, no vector DB, no GPU. Three Nemotron calls per brief (router → ranker → synthesis) and one PyMuPDF pass per new paper. Abstract-first ranking is the key cost lever — full text is only spent on the ~8 papers that survived the cheap filter.

Why it's interesting beyond the demo: the *insight-framed* synthesis prompt is anchored to the user's stated problem ("Reader is building X. From these papers produce: key findings, contradictions, what's matured vs. still open, and concrete recommendations.") — that framing is what turns a literature review into something actionable, and is the design idea the sample is selling.

---

## 2. Architecture delta from `vibe-coding-starter-kit`

| Keep (as-is) | Trim (remove from starter) | Add (new for this sample) |
|---|---|---|
| Monorepo layout (`apps/web` + `services/api` + `packages/shared`), pnpm workspaces | Generic file-upload UI: `/upload`, `/files`, dashboard with `stats-cards`, `upload-chart`, `recent-uploads-table` | Single `/` page: NL-question form + recent briefings list. `/briefings/[id]`: status card → rendered brief + paper cards. `/briefings`: archive |
| Next.js 16 App Router, Tailwind v4, shadcn/ui, TanStack Query, `next-themes` dark mode | `apps/web/src/app/upload/`, `apps/web/src/app/files/`, `components/upload/`, `components/files/`, `components/dashboard/` | `components/briefings/SubmitForm.tsx`, `BriefingStatusCard.tsx`, `BriefingViewer.tsx` (renders MD with citation links), `PaperCard.tsx`, `ArchiveList.tsx` |
| FastAPI layering: `types → config → repo → service → runtime` + `tests/test_structure.py` enforcement | `app/runtime/upload.py`, `app/runtime/files.py`, `app/service/upload.py`, `app/service/files.py`, `app/service/metadata.py`, `app/types/upload.py`, `app/types/files.py`, `app/types/formatting.py`, `app/types/stats.py` | `app/runtime/briefings.py` (POST submit, GET by id, GET list, DELETE), `app/runtime/papers.py` (presign one PDF). `app/service/topic_router.py`, `arxiv_search.py`, `abstract_ranker.py`, `pdf_pipeline.py`, `synthesis.py`, `pipeline.py` (orchestrator). `app/types/briefings.py`, `papers.py`, `arxiv.py` |
| `app/repo/b2_client.py` (boto3 + `@functools.lru_cache` client) — pattern is great, contents need surgery | Starter client uses the wrong sample user-agent, reads legacy endpoint/key-id settings, and **omits `region_name`** — all three diverge from the B2 sample standards | Rewritten `app/repo/b2_client.py` with `user_agent_extra="arxiv-insight-briefs/0.1.0 (backblaze-b2-samples)"`, `region_name=settings.b2_region`, derived S3 endpoint, and `aws_access_key_id=settings.b2_application_key_id`. New helpers: `head_object_or_none`, `put_bytes`, `get_text`, `list_prefix` |
| Structured JSON logging, `/health` (B2 connectivity), `/metrics` (Prometheus), CORS, lifespan setup from `main.py` | Health check assumes upload semantics — keep the bucket head-check, drop upload-specific fields from `/metrics` | `/metrics` gains `briefs_total`, `briefs_in_flight`, `papers_cache_hits_total`, `papers_cache_misses_total`, `nemotron_tokens_total{stage}`, `nemotron_errors_total{stage}` |
| `apps/web/src/lib/api-client.ts` + `lib/queries.ts` TanStack pattern — every fetch through a hook | `uploadFile()` XHR helper, `useFiles`, `useUpload`, `useFileMetadata`, `useDeleteFile` | `useSubmitBriefing`, `useBriefing(id)` (polls), `useBriefings()` (archive list), `useCancelBriefing(id)` |
| `packages/shared/src/types.ts` TS↔Python mirror discipline | `FileMetadata`, `FileMetadataDetail`, `FileStatus`, `UploadStats` | `BriefRequest`, `BriefStatus`, `BriefManifest`, `RankedPaper`, `InsightSection`, `Citation` |
| `scripts/doctor.mjs` predev preflight, `scripts/pick-port.mjs`, `scripts/dev.sh` | Doctor checks tied to upload-only env | Doctor adds: `NVIDIA_API_KEY` warn (not fail — graceful degrade), PyMuPDF wheel install hint, optional ffmpeg/curl checks dropped |
| pytest + ruff + `pnpm dev`/`dev:web`/`dev:api`/`lint`/`test:api`/`check:structure`/`test:e2e` | `tests/test_upload_*`, `test_delete*`, `test_download_*`, `test_recent_files.py`, `test_upload_activity.py`, `test_upload_conflict.py`, `test_health.py` (refit, not delete) | `tests/test_topic_router.py` (taxonomy validation, fake LLM), `test_arxiv_search.py` (fixture XML), `test_abstract_ranker.py`, `test_pdf_pipeline.py` (fake B2 + bundled tiny PDF fixture), `test_synthesis.py` (fake LLM, prompt-shape assertions), `test_pipeline.py` (end-to-end with all fakes), `test_briefings_api.py` (FastAPI test client) |
| LICENSE (MIT), `.pre-commit-config.yaml`, `pnpm-workspace.yaml`, `.gitignore` | `infra/railway/` (deployment is out of scope for this sample) | New `requirements.txt` adds: `httpx>=0.27`, `arxiv>=2.1`, `pymupdf>=1.24`, `tenacity>=8.5`. Drops: `python-magic`, `Pillow`, `PyPDF2`, `python-multipart` |
| Design system route `/design` + `components/design/*` — useful living style guide for new components | Design demos that reference upload/file primitives | `/design` retained; one new section added showing `BriefingViewer` + `PaperCard` primitives |
| `components/layout/header.tsx`, `app-sidebar.tsx`, `command-palette.tsx`, `health-banner.tsx`, `theme-provider.tsx` | Header brand label `oss-starter-kit`; sidebar links pointing at `/upload`, `/files`; command-palette upload actions | Header brand label `arxiv-insight-briefs`; sidebar links: New brief, Archive, Design, Settings; command-palette: "New brief", "Open latest brief", "Open archive" |
| `apps/web/src/app/settings/` (B2 connectivity panel + danger zone wired to API health) | Danger-zone "delete all files" action (not appropriate here) | Settings: shows B2 status, NVIDIA endpoint reachability, last `nemotron_errors_total`. Danger zone: "clear cached briefings" (deletes only `briefs/` prefix in this sample, never `papers/`) |

**Why not strip more?** The starter's value is the agent-friendly scaffolding (AGENTS.md, structural tests, JSON logging, doctor.mjs, TanStack discipline). Keeping the design system route and settings page costs almost nothing and signals to readers that this is a "real" sample, not a one-route demo.

---

## 3. B2 surface

Per parent `CLAUDE.md`: **S3-compatible API only (`boto3`)**. No b2-native API anywhere.

S3 operations exercised:

| Op | Where used | Why |
|---|---|---|
| `HeadObject` | `pdf_pipeline.fetch_paper()` before arxiv download; `pdf_pipeline.load_extracted()` before re-extraction | Cache check — this is the *demo* B2 idea, surfaced as `papers_cache_hits_total` |
| `PutObject` | PDF cache (`papers/{arxiv_id}.pdf`), extracted text cache (`papers/{arxiv_id}.txt`), brief markdown (`briefs/{id}/brief.md`), brief manifest (`briefs/{id}/manifest.json`), original NL query (`briefs/{id}/query.json`) | All durable artifacts |
| `GetObject` | Read cached extracted text for synthesis; serve brief markdown to UI | Reuse the cache; UI never round-trips through the API for static brief content |
| `GeneratePresignedUrl` (GET) | Per-citation PDF link (1h expiry), per-brief markdown link for sharing | Three demo flavors of presigning |
| `ListObjectsV2` | `/briefings` archive page (prefix `briefs/`); cache audit endpoint (`papers/`) | "Past briefings" feed, observability of the cache |
| `DeleteObject` / `DeleteObjects` | Settings → "clear cached briefings" deletes only `briefs/{id}/*` for a given id | Never deletes `papers/` to preserve the shared cache |

No b2-native API. No multipart upload (PDFs are < 20 MB; arxiv caps source size much lower in practice).

Object layout in B2:

```
b2://{B2_BUCKET_NAME}/arxiv-insight-briefs/
  papers/
    {arxiv_id}.pdf          # content-addressed PDF cache (shared across briefs)
    {arxiv_id}.txt          # section-trimmed extracted text cache
  briefs/
    {brief_id}/
      query.json            # original NL question + LLM-resolved categories/keywords
      manifest.json         # schema-versioned: ranked papers, paths, status, timings
      brief.md              # the generated insight briefing (markdown)
```

`{arxiv_id}` is sanitized (arxiv ids contain `.` and `/` for some legacy entries — normalize to `2401.12345v1`-style). `{brief_id}` is `uuid4`. All operations through `app/repo/b2_client.py`; structural test asserts no `boto3` imports outside `app/repo/`.

---

## 4. Key features

1. **NL topic → arxiv routing.** Single Nemotron call converts free-text question into `{categories: ["cs.NI", "cs.DC"], keywords: ["file transfer", "QUIC", "BBR"], time_window_months: 12}`. Validated against the static arxiv taxonomy list bundled in `app/repo/arxiv_taxonomy.py` (hallucinated codes are dropped; if all are dropped, fall back to keyword-only search across `cs.*`).
2. **Two-stage relevance filter.** arxiv API returns ~50 candidates by metadata; a single batched Nemotron call scores all abstracts against the user's question and returns the top ~8. This is the cost lever — full text is *only* spent on the survivors.
3. **B2 as content-addressed PDF + extraction cache.** `HeadObject` check before any arxiv re-fetch and before any PyMuPDF re-pass. Cache key = sanitized arxiv id. Surfaced in UI as a "served from cache" badge per paper card. Cache hits/misses exported on `/metrics`.
4. **Section-aware PyMuPDF extraction.** Heuristic header detection keeps `abstract + intro + methods + conclusion` and drops references, related-work, appendices. Stays under a fixed token budget per paper so 8 papers fit in one synthesis call.
5. **Insight-framed synthesis.** One Nemotron call produces structured sections: `key_findings[]`, `contradictions[]`, `maturity_assessment` (mature / emerging / open), `recommendations_for_reader[]`, `open_questions[]`. Every claim carries `citations: [arxiv_id, ...]`. UI renders citations as clickable presigned PDF links.
6. **Briefing archive in B2.** Every generated brief saved durably under `briefs/{id}/`. `/briefings` page lists them (via `ListObjectsV2 prefix=briefs/`), opens at `/briefings/[id]`. The bucket *is* the archive — no database.

Deliberately *not* in v1 (to honor "least resource intensive" and "ships in a weekend"):
- Single-paper deep-dive Q&A. Documented as the natural next step in `docs/exec-plans/active/follow-ups.md`.
- Embeddings / vector DB / RAG over the corpus. Out of scope; mention in README as the "if you outgrow this, here's what to add next" pointer.
- Multi-tenant brief storage. Sample is single-user.

---

## 5. Doc transforms

**Rewrite (keep filename, replace contents):**

- `README.md` — new pitch (one-paragraph problem statement, the insight-framing idea, what the brief looks like), pipeline diagram (ASCII), env setup, free-tier model notes, graceful-degradation behavior, *limitations* section (no Q&A, no embeddings, abstract-only ranker, AGPL note on PyMuPDF).
- `AGENTS.md` — same control-surface header; doc-read order points at new feature files; commands section unchanged; doc-update mapping updated to reference new feature docs.
- `ARCHITECTURE.md` — replace the upload/download data flow with the brief pipeline flow; layer table unchanged; structural-test contract unchanged; B2 object layout diagram added.
- `CLAUDE.md` (sample-level, top of tree) — slug + doc-read order updated; pointers updated.
- `.env.example` — B2 sample standard names: `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, `B2_PUBLIC_URL_BASE`. Sample-specific: `NVIDIA_API_KEY`, `NVIDIA_NEMOTRON_MODEL` (default `mistralai/mistral-nemotron`), `NVIDIA_BASE_URL` (default `https://integrate.api.nvidia.com/v1`), `ARXIV_CANDIDATE_LIMIT` (default `50`), `BRIEF_PAPER_LIMIT` (default `8`), `BRIEF_TIME_WINDOW_MONTHS` (default `12`), `MAX_BRIEFS_IN_FLIGHT` (default `2`).
- `CODE_REVIEW.md` — keep structure; replace upload-specific rules with: `httpx` only in `app/repo/`, no LLM prompt strings outside `app/service/`, no PyMuPDF imports outside `app/repo/pdf_extractor.py`, prompt files live in `app/service/prompts/`.
- `package.json` (root + `apps/web/package.json` + `packages/shared/package.json` + `apps/web/next.config.ts`) — `name` and workspace-filter references switch to `arxiv-insight-briefs`.
- `services/api/requirements.txt` — drop `python-magic`, `Pillow`, `PyPDF2`, `python-multipart`. Add `httpx>=0.27`, `arxiv>=2.1`, `pymupdf>=1.24`, `tenacity>=8.5`.
- `services/api/main.py` — drop multipart routes; register new `briefings` + `papers` routers; keep `health`, `metrics`.
- `apps/web/src/components/layout/header.tsx` — brand label `oss-starter-kit` → `arxiv-insight-briefs`.
- `apps/web/src/components/layout/app-sidebar.tsx`, `command-palette.tsx` — nav items updated.
- `docs/SECURITY.md` — keep file; rewrite for: NVIDIA API key handling, prompt-injection consideration from arxiv abstracts (treat abstracts as untrusted input even though arxiv is curated; never let abstract text reach a system role), presigned URL expiry, .env discipline. Drop file-upload size-limit content.
- `docs/RELIABILITY.md` — keep file; rewrite for: `MAX_BRIEFS_IN_FLIGHT` semaphore, atomic per-brief state file, partial-success surfacing (some papers may fail PDF fetch or extraction — manifest records which), cache discipline.
- `docs/app-workflows.md` — submit → status polling → done flow; cancel flow; archive flow.
- `docs/dev-workflows.md` — keep file; only the testing recipe blocks change.

**Stub new feature docs** (using `docs/features/_template.md` shape):

- `docs/features/topic-routing.md` — LLM-as-router contract, taxonomy validation, fallback to keyword-only.
- `docs/features/paper-discovery.md` — arxiv API query construction, candidate fetch, abstract ranking.
- `docs/features/pdf-pipeline.md` — B2 cache lookup, arxiv PDF fetch, PyMuPDF extraction, section-trim heuristic, cache write.
- `docs/features/insight-synthesis.md` — synthesis prompt, JSON output schema, citation mapping, token budget.
- `docs/features/briefing-archive.md` — `ListObjectsV2`-backed feed, presigned share links, "clear cached briefings" semantics.

**Delete (not relevant to this sample):**

- `docs/features/file-upload.md`, `file-browser.md`, `dashboard.md`, `metadata-extraction.md`
- `infra/railway/` (deployment is out of scope)
- `docs/images/b2-starterkit-*.png` (replace with one new pipeline diagram image only if quick to generate — otherwise leave images out of v1 and stub a TODO; do **not** commit binary screenshots without user approval)

**Move on finalize:**

- This scratch plan → `./arxiv-insight-briefs/docs/exec-plans/completed/initial-scaffold.md`.

---

## 6. Rename table

Every identifier that must change from `vibe-coding-starter-kit` to `arxiv-insight-briefs`. Every entry below was verified against the starter tree (`grep -rIn 'vibe-coding-starter-kit\|vibe_coding_starter_kit\|b2ai-oss-start\|oss-starter'`).

| Identifier kind | From (starter) | To (this sample) |
|---|---|---|
| Directory / repo slug (kebab) | `vibe-coding-starter-kit` | `arxiv-insight-briefs` |
| Python package name (snake) | `vibe_coding_starter_kit` (n/a as a top-level pkg today; modules live under `app/`) | `arxiv_insight_briefs` (only if introduced as a top-level pkg name; otherwise keep `app/` and don't introduce one) |
| Title Case (docs, README headings) | `Vibe Coding Starter Kit` | `arXiv Insight Briefs` *(stylized lowercase "arXiv" per arxiv.org branding)* |
| `package.json` `name` (root) | `vibe-coding-starter-kit` | `arxiv-insight-briefs` |
| `package.json` `name` (apps/web) | `@vibe-coding-starter-kit/web` | `@arxiv-insight-briefs/web` |
| `package.json` `name` (packages/shared) | `@vibe-coding-starter-kit/shared` | `@arxiv-insight-briefs/shared` |
| Workspace filter in scripts | `pnpm --filter @vibe-coding-starter-kit/web …` | `pnpm --filter @arxiv-insight-briefs/web …` (root `package.json` lines 8, 10, 11, 15) |
| `next.config.ts` `transpilePackages` | `["@vibe-coding-starter-kit/shared"]` | `["@arxiv-insight-briefs/shared"]` |
| All TS source imports | `from "@vibe-coding-starter-kit/shared"` | `from "@arxiv-insight-briefs/shared"` (9 files: `command-palette.tsx`, `file-preview.tsx`, `file-metadata-panel.tsx`, `file-browser.tsx`, `queries.ts`, `upload-progress.tsx`, `api-client.ts`, `file-tree.ts`, plus any new ones — note several of these *files* are being deleted in the trim step; rename only survives in `queries.ts` and `api-client.ts`) |
| Frontend brand label | `oss-starter-kit` in `components/layout/header.tsx:60` | `arxiv-insight-briefs` |
| Custom S3 user-agent string | `user_agent_extra="b2ai-oss-start"` in `repo/b2_client.py:45` | `user_agent_extra="arxiv-insight-briefs/0.1.0 (backblaze-b2-samples)"` |
| `pyproject.toml` `name` (if present) | (verify in build phase; starter may use `requirements.txt` only) | `arxiv-insight-briefs-api` if a `pyproject.toml` is needed |
| B2 env var: endpoint | legacy explicit endpoint variable | derive S3 endpoint from `B2_REGION` |
| B2 env var: key id | starter-specific key-id variable | `B2_APPLICATION_KEY_ID` *(also use `settings.b2_application_key_id` in `app/config/settings.py` + every reader)* |
| B2 env var: region | **(absent in starter — bug)** | `B2_REGION` *(add to `.env.example`, settings, and pass as `region_name=` to boto3)* |
| B2 env var: application key | `B2_APPLICATION_KEY` | `B2_APPLICATION_KEY` (unchanged) |
| B2 env var: bucket | `B2_BUCKET_NAME` | `B2_BUCKET_NAME` (unchanged) |
| B2 env var: public URL base | **(absent in starter — bug)** | `B2_PUBLIC_URL_BASE` |
| Frontend API base env | `NEXT_PUBLIC_API_URL` | `NEXT_PUBLIC_API_URL` (unchanged) |
| Top-level B2 object prefix | n/a in starter (root-bucket uploads) | `arxiv-insight-briefs/` (then `papers/…`, `briefs/…`) |
| Image / docker tag references | none in starter | n/a — no Docker in this sample |
| GitHub workflow slug references | none material | `arxiv-insight-briefs-*` if any workflows are added |
| UTM `content` tag in README/Backblaze links | `utm_content=oss-starter` (3 places in `README.md`) | `utm_content=arxiv-insight-briefs` |
| Clone URL example | `github.com/backblaze-b2-samples/vibe-coding-starter-kit.git` | `github.com/backblaze-labs/arxiv-insight-briefs-nvidia-nemotron.git` |
| Initial-commit message example | `"Initial commit from vibe-coding-starter-kit"` | `"Initial commit from arxiv-insight-briefs"` |
| `.claude/settings.local.json` filter strings | `pnpm --filter @vibe-coding-starter-kit/web …` (4 lines) | `pnpm --filter @arxiv-insight-briefs/web …` |
| LICENSE attribution | MIT — preserve as-is | preserve MIT; update copyright line only if it bears the old slug |
| `docs/SECURITY.md:4` self-reference | `"…for the vibe-coding-starter-kit."` | `"…for the arxiv-insight-briefs sample."` |

**Builder note:** treat `pnpm-lock.yaml` as a single rename target rather than re-resolving — it has one matching line and a manual edit there is fine. Do not run `pnpm install` as part of the rename step; the build phase will do a single fresh install at the end.

---

## 7. Failure modes the builder should design for up front

These are the edge cases that, if not in v1, will be the first three issues the user files. Calling them out here so the builder addresses them in the initial code rather than as follow-ups.

1. **LLM hallucinates a category that doesn't exist.** Validate router output against bundled `arxiv_taxonomy.py`. If *all* returned categories are invalid, drop to keyword-only search across `cs.*` and surface a `warning` in the manifest.
2. **arxiv returns zero candidates.** Don't crash — set brief status to `done_no_results`, write a `brief.md` that says "no recent papers matched; try broadening the question" with the resolved query echoed back.
3. **PDF fetch or extraction fails for one paper.** Skip that paper, continue. The manifest records `{arxiv_id, status: "extraction_failed", error: "…"}`. Synthesis runs on whatever succeeded; brief surfaces a "N of M papers" footnote.
4. **NVIDIA endpoint rate-limited or 5xx.** `tenacity` retry (exp backoff, max 2 retries) inside `app/repo/nemotron_client.py`. After retries: brief status `failed_llm`, surface the upstream error to the UI; PDFs already cached stay cached (no rollback).
5. **No `NVIDIA_API_KEY` set.** Graceful degrade: router and synthesis stages skip, brief status `done_no_analysis`, manifest still records the arxiv candidates and any cached papers. UI renders an explainer instead of the brief body. The B2 half of the sample is fully usable with B2 credentials alone.
6. **Prompt-injection from a paper abstract or PDF body.** Abstracts and extracted text are treated as untrusted: never appear in a `system` role, always wrapped in a `<paper id="…">…</paper>` envelope inside the `user` message, and the system prompt explicitly instructs the model to ignore embedded instructions. Documented in `docs/SECURITY.md`.
7. **Token budget overflow.** Section-trim is a soft heuristic. Hard cap: per-paper text truncated to `MAX_PAPER_CHARS` (default 12k) before going into the synthesis call. If `MAX_PAPER_CHARS * BRIEF_PAPER_LIMIT` would still exceed model context, reduce paper count automatically and record the reduction in the manifest.
8. **Cooperative cancellation.** `DELETE /briefings/{id}` sets `cancel_requested: true` in the state file; pipeline checks it between stages. README documents that an in-flight network read won't die immediately.

---

## 8. Build sequence (suggested order for the builder)

1. Clone-and-strip: copy `vibe-coding-starter-kit` → `arxiv-insight-briefs`, strip git history, delete trim list (Section 2).
2. Mechanical rename pass (Section 6) — single sweep with verification grep at the end.
3. Fix the three B2 standards bugs in `app/repo/b2_client.py` and `app/config/settings.py` (env var names + add `B2_REGION`).
4. New types in `app/types/` and `packages/shared/src/types.ts` (Section 2 add row).
5. New repo layer: `arxiv_client.py`, `nemotron_client.py`, `pdf_extractor.py`, `job_state.py`, `arxiv_taxonomy.py`.
6. New service layer: `topic_router.py`, `arxiv_search.py`, `abstract_ranker.py`, `pdf_pipeline.py`, `synthesis.py`, `pipeline.py`, plus `service/prompts/` for the three prompt strings.
7. New runtime layer: `briefings.py`, `papers.py` routers; register in `main.py`.
8. Strip + rewrite tests; add new tests with fakes for `nemotron_client` and `arxiv_client` so the suite runs offline.
9. Frontend: replace pages, rewrite components, update `api-client.ts` and `queries.ts`.
10. Doctor.mjs adjustments; `.env.example`; root README + docs.
11. Verification pass: `pnpm doctor && pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`. All must pass.
12. Final grep: zero hits for `vibe-coding-starter-kit`, `vibe_coding_starter_kit`, `b2ai-oss-start`, `oss-starter` outside `docs/exec-plans/completed/initial-scaffold.md` (which legitimately references them as the source template).

---

## 9. Open questions / decisions deferred to the builder

These are intentional latitude — the builder should pick a sensible default, document it, and move on, not block on confirmation:

- Exact Nemotron model id on `build.nvidia.com`. If `mistralai/mistral-nemotron` isn't available on the free tier at build time, fall back to `meta/llama-3.3-70b-instruct` and note the swap in README.
- Whether to ship a tiny fixture PDF in `tests/fixtures/` for `pdf_pipeline` tests, or generate one programmatically. Either is fine; programmatic generation keeps the repo smaller.
- Whether to render the brief markdown server-side or client-side. Default: client-side via `react-markdown` (already an idiomatic choice; cheap; works with citation link rewrites).

---

## 10. Out of scope (explicit)

- Multi-user accounts, sharing, auth
- Embeddings, vector DB, semantic search
- Single-paper Q&A / chat interface
- Cron jobs / scheduled briefings
- Mobile-first layout
- Internationalization
- Cost telemetry / billing UI for NVIDIA usage
- Docker / Railway / any deployment config

These are listed so the reviewer doesn't flag them as gaps.

---

## Post-scaffold revision (2026-05-26)

Per user request after the first-run smoke test, the file browser was
restored from the starter (`/files` route, `app/runtime/files.py`,
`app/service/files.py`, `app/service/metadata.py`, `app/types/files.py`,
plus the corresponding React components and TanStack hooks). The user
explicitly chose **full CRUD, no guard on `papers/`** — anything under
the sample's B2 prefix can be deleted from the UI, including cached
PDFs. This contradicts §2 (trim list above), which removed the file
browser entirely. Rationale: bucket observability outweighs a safety
rail in a single-developer sample; an accidentally-deleted paper costs
one re-fetch on the next briefing run, not data loss. The Pillow /
PyPDF2 dependencies the starter used for richer image / PDF detail were
**not** restored — the detail panel degrades gracefully to a "no
detailed metadata available" hint for those mime types. See
`docs/features/file-browser.md`.

The same revision pass also hardened arxiv 429 handling in
`app/repo/arxiv_client.py` and added a `failed_arxiv_rate_limit` brief
status — see `docs/features/paper-discovery.md` -> "Rate limit handling"
for the policy.
