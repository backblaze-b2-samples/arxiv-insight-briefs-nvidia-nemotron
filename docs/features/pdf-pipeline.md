<!-- last_verified: 2026-05-26 -->
# Feature: PDF Pipeline (cache + extract)

## Purpose
For each ranked paper, ensure the PDF and its section-trimmed text live
in B2, returning the text for downstream synthesis. Cache-first so
overlapping queries cost zero arxiv re-fetches and zero PyMuPDF re-passes.

## Used By
- API: `pipeline.py` `fetching_pdfs` stage — called once per ranked paper

## Core Functions
- `app.service.pdf_pipeline.fetch_and_extract`
- `app.repo.b2_client.object_exists` / `put_bytes` / `get_bytes`
- `app.repo.arxiv_client.download_pdf`
- `app.repo.pdf_extractor.extract_section_trimmed_text`

## Canonical Files
- `services/api/app/service/pdf_pipeline.py`
- `services/api/app/repo/pdf_extractor.py`
- `services/api/app/repo/job_state.py` (key helpers)

## Inputs
- `RankedPaper` (we use `arxiv_id` and `pdf_url`)
- `settings.max_paper_chars` (hard cap fed to extractor)

## Outputs
- `PaperFetchResult(arxiv_id, text, cached, status, error)` where
  `status ∈ {"ok", "fetch_failed", "extract_failed"}`
- Side effects:
  - `papers/{arxiv_id}.pdf` written on first fetch (PUT)
  - `papers/{arxiv_id}.txt` written on first extract (PUT)
  - `papers_cache_hits_total` / `papers_cache_misses_total` incremented

## Flow
1. HEAD `papers/{id}.pdf` — set `pdf_cached`.
2. If not cached → `arxiv_client.download_pdf` (httpx, follow_redirects),
   then PUT the bytes.
3. HEAD `papers/{id}.txt` — if present, GET and return (PDF-cached counter
   reflects the PDF state, not the text state, by design).
4. Otherwise extract via PyMuPDF: read all pages, drop everything after
   `references|bibliography|acknowledg|appendix`, collapse blank-line
   runs, hard-truncate to `max_paper_chars`.
5. PUT the extracted text (best-effort — synthesis proceeds even if the
   text-cache write fails).

## Edge Cases
- PDF fetch fails → `fetch_failed`; recorded on the paper's manifest entry
- Extraction throws (corrupt PDF) → `extract_failed`; recorded
- B2 PUT for the cached PDF fails but bytes are in hand → still extract
  and try to write text cache; log a warning rather than aborting
- Text cache write fails → returned `text` is still valid; synthesis runs
- All papers fail extraction → pipeline routes to `done_no_analysis`
- `max_paper_chars * brief_paper_limit` exceeds model context → caller
  should reduce paper count (documented as a follow-up; v1 caps per-paper
  only)

## Verification
- Test file: `services/api/tests/test_pdf_pipeline.py`
- Required cases: cache-hit short circuit; fresh-fetch happy path;
  fetch_failed; extract_failed; partial cache (PDF cached but no text)
- Test fixture: tiny PDF generated programmatically (no binary in-tree)
- Quick verify: `pnpm test:api -- tests/test_pdf_pipeline.py`
- Pass criteria: zero network calls on cache hit; counters reflect
  hits/misses correctly

## Related Docs
- [docs/features/paper-discovery.md](paper-discovery.md)
- [docs/features/insight-synthesis.md](insight-synthesis.md)
- [docs/RELIABILITY.md](../RELIABILITY.md) — partial-success contract
