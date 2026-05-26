<!-- last_verified: 2026-05-26 -->
# App Workflows

User journeys for the arxiv-insight-briefs UI.

## Submit a brief

- User lands on `/` (New brief). Form: NL question + time window (months).
- Submitting calls `POST /briefings` via `useSubmitBriefing`.
- API acquires an in-flight slot (503 if `MAX_BRIEFS_IN_FLIGHT` saturated),
  persists a queued manifest to B2, schedules a background task, and
  returns `{ brief_id, status: "queued" }`.
- UI navigates to `/briefings/{id}` immediately.

## Watch a brief progress

- `/briefings/{id}` mounts and calls `useBriefing(id)`.
- The hook polls `GET /briefings/{id}` every 2s while status is in-flight
  (`queued` → `routing` → `searching` → `ranking` → `fetching_pdfs` →
  `synthesizing`). Polling stops at any terminal status.
- The status card shows the current stage, cache hit/miss counters, the
  "router fallback used" hint when applicable, and a Cancel button while
  the brief is still moving.
- Once `done`, the brief markdown and the source-papers grid render.
  Citations in the brief are clickable presigned links to the cached
  PDFs in B2.
- See: [insight-synthesis](features/insight-synthesis.md), [pdf-pipeline](features/pdf-pipeline.md).

## Cancel a brief

- From `/briefings/{id}`, click **Cancel**.
- UI calls `DELETE /briefings/{id}?mode=cancel`.
- The API flips `cancel_requested: true` on the manifest. The pipeline
  checks the flag between stages and transitions to `cancelled` at the
  next checkpoint. An in-flight HTTP read won't die immediately — the
  user sees `cancelled` after the current network call returns.

## Browse the archive

- `/briefings` lists every brief in B2, newest first.
- Each row shows the question, brief id (first 8 chars), created date,
  paper count, and status. Clicking opens the detail page.
- The list is sourced live from `ListObjectsV2` over `briefs/` — there
  is no database to keep in sync.
- See: [briefing-archive](features/briefing-archive.md).

## Open a source paper

- From `/briefings/{id}`, click any citation badge (e.g. `arxiv:2401.12345`)
  inside the rendered brief, or click **Open PDF** on a paper card.
- The badge target is a short-lived B2 presigned GET URL (1h default).
  The browser fetches the PDF straight from B2 — the API is not in the
  data path.

## Health banner

A degraded-state banner appears at the top of every page when the API
reports `b2_connected: false`. This is the case where individual fetches
might succeed silently against an empty cache — the banner makes the
misconfiguration loud. Polled every 60s and on window focus.
