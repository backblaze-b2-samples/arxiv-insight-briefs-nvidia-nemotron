<!-- last_verified: 2026-05-26 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| Pipeline state isn't auto-resumed after API restart | Briefs stuck mid-pipeline forever | Add a startup janitor that surveys `briefs/*/manifest.json` for non-terminal status and either re-queues or marks them `failed` with a clear reason | Medium | Open |
| `MAX_PAPER_CHARS * BRIEF_PAPER_LIMIT` could still exceed model context | Synthesis call may 4xx with a long body | Sum char count before the synthesis call and reduce `brief_paper_limit` automatically, recording the reduction in the manifest | Medium | Open |
| Single-paper deep-dive Q&A not implemented | Limits the sample's "what's next" story | Add a `/briefings/{id}/papers/{arxiv_id}/ask` endpoint + minimal RAG over the cached extracted text | Low | Open |
| Brief markdown is rendered via a tiny in-house renderer | No syntax-highlight, no tables, no nested lists | Swap to `react-markdown` once the styles settle | Low | Open |
| PyMuPDF is AGPL — okay for a sample but a problem for commercial forks | License risk for downstream users | Document the swap path (pypdfium2 / pdfminer.six) in README; consider shipping it behind a setting | Medium | Open (documented in README) |
| No background-task supervision | A crashed pipeline task leaves no trace beyond the manifest | Wrap `pipeline.run_brief` in a supervisor that logs + emits a metric on uncaught errors | Low | Open |
