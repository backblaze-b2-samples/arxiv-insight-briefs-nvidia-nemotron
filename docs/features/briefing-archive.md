<!-- last_verified: 2026-05-26 -->
# Feature: Briefing Archive

## Purpose
B2 is the archive. Every generated brief lives at `briefs/{id}/` and is
discoverable via `ListObjectsV2`. There is no database, no Redis, no
side-channel index — the bucket is the source of truth.

## Used By
- UI: `/briefings` archive page (and the home page's "Recent briefings"
  sidebar) via `useBriefings()`
- UI: command palette "Recent briefings" group
- Sharing: a generated brief's presigned markdown link is itself a
  shareable artifact

## Core Functions
- `app.service.briefings.list_briefs`
- `app.service.briefings.get_manifest`
- `app.service.briefings.cancel_brief`
- `app.service.briefings.clear_brief`
- `app.service.briefings.render_citations_to_links`
- `app.repo.b2_client.list_prefix`
- `app.repo.b2_client.delete_prefix`

## Canonical Files
- `services/api/app/service/briefings.py`
- `services/api/app/runtime/briefings.py`
- `services/api/app/repo/b2_client.py`
- `apps/web/src/components/briefings/ArchiveList.tsx`

## Inputs
- `limit: int` (max items, capped at 500 server-side)
- For cancel/clear: `brief_id: str`

## Outputs
- `GET /briefings` → `list[BriefSummary]`
- `GET /briefings/{id}` → `BriefDetail` (manifest + rewritten markdown)
- `DELETE /briefings/{id}?mode=cancel` → 204 (flips manifest flag)
- `DELETE /briefings/{id}?mode=clear` → 204 (deletes `briefs/{id}/*`)

## Flow (list)
1. `list_prefix("briefs/", max_keys=limit*10)` returns object summaries.
2. For every key ending in `/manifest.json`, load the manifest and emit
   a `BriefSummary` row.
3. Sort by `created_at` descending; truncate to `limit`.

## Flow (detail with presigned citations)
1. `load_manifest(id)` from B2; 404 if absent.
2. `attach_citations` overlays each `RankedPaper.pdf_url` with a
   presigned GET URL for the cached PDF (so paper-card "Open PDF" links
   serve directly from B2).
3. `get_brief_markdown(id)` reads `briefs/{id}/brief.md`.
4. `render_citations_to_links` rewrites every `[arxiv:ID]` whose id is
   known to the manifest into `[arxiv:ID](presigned-url)`.
5. Return `{manifest, markdown}`.

## Edge Cases
- Manifest exists but markdown does not (in-flight brief) → `markdown` is `null`
- Citation references an id not in the manifest → left inert
- `mode=clear` on a missing brief → 404
- `delete_prefix("")` or `delete_prefix(settings.b2_key_prefix)` → repo
  guard raises `ValueError`, never bombs the bucket
- `mode=cancel` on a completed brief → no-op, still returns 204

## Verification
- Test file: `services/api/tests/test_briefings_api.py`
- Required cases: list returns newest-first; detail with markdown
  rewrites citations; cancel toggles `cancel_requested`; clear removes
  prefix; cancel/clear on missing id returns 404
- Quick verify: `pnpm test:api -- tests/test_briefings_api.py`
- Pass criteria: archive is consistent with B2 state without any
  side-channel index

## Related Docs
- [docs/features/insight-synthesis.md](insight-synthesis.md) — where citations come from
- [docs/SECURITY.md](../SECURITY.md) — presigned URL posture
- [docs/RELIABILITY.md](../RELIABILITY.md) — cancel semantics
