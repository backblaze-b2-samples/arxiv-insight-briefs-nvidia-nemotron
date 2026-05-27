<!-- last_verified: 2026-05-26 -->
# Feature: File Browser

## Purpose
Read-write explorer over the configured B2 prefix so the user can verify
what the briefing pipeline writes, inspect cached PDFs, and clean up
artifacts directly from the UI. Restored from the upstream starter
template per user request after the first-run smoke test
(see `docs/exec-plans/completed/initial-scaffold.md`).

## Scope decision
Full CRUD, no guard on `papers/`. The user explicitly chose bucket
observability over a safety rail — anything under the sample's B2 prefix
can be deleted from this page, including cached papers. The briefing
pipeline will simply re-fetch the next time it sees the same arxiv id,
so accidental deletion costs one extra HTTP round-trip, not data loss.

## Used By
- UI: `/files` route, plus a "Files" entry in the sidebar and command
  palette ("Open files", "Browse papers cache")
- API: `GET /files`, `GET /files/{key}/metadata`,
  `GET /files/{key}/download`, `DELETE /files/{key}`

## Core Functions
- `app.service.files.list_files` / `get_file` / `get_download_url` / `remove_file`
- `app.service.metadata.get_metadata`
- `app.repo.b2_client.list_prefix` / `head_object_or_none` / `presign_get` / `delete_object`
- Frontend: `useFiles`, `useFileMetadata`, `useDeleteFile` (TanStack hooks)

## Canonical Files
- `services/api/app/runtime/files.py`
- `services/api/app/service/files.py`
- `services/api/app/service/metadata.py`
- `services/api/app/types/files.py`
- `apps/web/src/app/files/page.tsx`
- `apps/web/src/components/files/file-browser.tsx`
- `apps/web/src/components/files/file-metadata-panel.tsx`
- `apps/web/src/lib/file-tree.ts`

## Inputs
- `prefix`: query-string filter for `GET /files`
- `key`: URL-encoded object key path for per-object endpoints

## Outputs
- `list[FileMetadata]` (sorted newest-first)
- `FileMetadataDetail` from HEAD (size, mime, etag, last-modified)
- 302 redirect to a presigned GET URL for downloads
- `{deleted: true, key}` on DELETE

## Flow (list)
1. UI calls `useFiles()` -> `GET /files?prefix=&limit=200`
2. Runtime -> `service.files.list_files`
3. Service -> `repo.b2_client.list_prefix` (paginated `ListObjectsV2`)
4. Each row projected onto `FileMetadata` with mimetype guessed from
   extension; sorted desc by `LastModified`
5. Frontend `buildFileTree()` turns the flat list into a folder hierarchy

## Flow (delete)
1. UI confirms via AlertDialog (no per-prefix branching)
2. `DELETE /files/{key}` -> `service.files.remove_file`
3. Service validates the key (path-traversal regex) then calls
   `repo.b2_client.delete_object`
4. On success, `useDeleteFile` invalidates the entire `b2` query key —
   the files list, the briefings archive, and any cached metadata all
   refetch lazily

## Edge Cases
- Empty key or `..`/null-byte in key -> 400 `Invalid file key`
- Missing object -> 404 `File not found`
- B2 transient failure -> 500 `Failed to delete file`; toast surfaces it
- Image / PDF object inspected -> detail panel shows a "no detailed
  metadata available" hint because this sample omits Pillow / PyPDF2

## UX States
- Loading -> skeleton rows
- Error -> `ErrorState` with retry
- Empty -> `EmptyState` ("This bucket prefix is empty")
- Populated -> collapsible tree, top-level folders auto-expanded on
  first load, expansion state preserved on refresh

## Verification
- Test file: `services/api/tests/test_files_api.py`
- Required cases:
  - list with no prefix
  - list with prefix
  - get metadata (200 + 404)
  - delete (200 + 404 + 500 propagation)
  - delete of a `papers/` object is allowed (no guard)
- Quick verify: `pnpm test:api -- tests/test_files_api.py`
- Pass criteria: every test passes; `papers/`-deletion test asserts the
  request returns 200 and the object is gone from the in-memory store

## Related Docs
- [docs/features/briefing-archive.md](briefing-archive.md)
- [docs/features/pdf-pipeline.md](pdf-pipeline.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
