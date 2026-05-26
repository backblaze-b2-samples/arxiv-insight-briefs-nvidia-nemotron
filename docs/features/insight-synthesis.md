<!-- last_verified: 2026-05-26 -->
# Feature: Insight Synthesis

## Purpose
Turn the surviving paper texts into a problem-anchored markdown brief.
This is the one stage where the user's framing of the problem
*explicitly anchors* the model — it's why the output reads as advice for
"someone building X" rather than a literature summary.

## Used By
- API: `pipeline.py` final `synthesizing` stage
- UI: `/briefings/{id}` renders the resulting markdown

## Core Functions
- `app.service.synthesis.synthesize`
- `app.service.synthesis.build_no_analysis_brief` / `build_no_results_brief`
- `app.service.prompts.synthesis.SYNTHESIS_SYSTEM` / `build_synthesis_user`
- `app.service.briefings.render_citations_to_links`

## Canonical Files
- `services/api/app/service/synthesis.py`
- `services/api/app/service/prompts/synthesis.py`
- `services/api/app/service/briefings.py` (citation rewrite)

## Inputs
- `question: str` (the user's NL question, unchanged from submission)
- `paper_blobs: list[tuple[arxiv_id, extracted_text]]`

## Outputs
- `(markdown: str | None, usage: dict[str, int])`
- Markdown structure (enforced by system prompt):
  1. Key Findings
  2. Contradictions & Open Debate
  3. Maturity Assessment
  4. Recommendations for the Reader
  5. Open Questions
- Citations use `[arxiv:ID]` tokens; the runtime layer rewrites them to
  presigned PDF links before serving to the UI.

## Flow
1. `synthesis.synthesize` calls `nemotron_client.chat_completion` with
   the question and each paper blob wrapped in `<paper id="…">…</paper>`.
2. Returns the model's markdown body plus token usage.
3. The pipeline writes the markdown to `briefs/{id}/brief.md` and stamps
   `nemotron_tokens["synthesis"]` on the manifest.
4. On read (`GET /briefings/{id}`), `render_citations_to_links` rewrites
   every `[arxiv:ID]` whose id appears in the manifest's ranked papers
   to a presigned GET link for `papers/{id}.pdf`.

## Fallback paths
- `NemotronNotConfigured` or persistent `NemotronError` → caller writes a
  skeleton brief via `build_no_analysis_brief` and sets status to
  `done_no_analysis`.
- arxiv returned 0 candidates → `build_no_results_brief` writes a friendly
  "try broadening" body and status `done_no_results`.

## Edge Cases
- Model invents an `[arxiv:HACKER]` token → citation-rewrite leaves it
  inert (not a clickable link); the only ids it expands are those in the
  manifest
- Model emits ```markdown fences → rendered as-is (we strip fences only
  when parsing JSON, not markdown bodies)
- Empty paper list → fall through to no-analysis skeleton
- Brief exceeds 900 words (prompt soft cap) → rendered as-is; trimming
  is not enforced server-side

## Verification
- Test file: `services/api/tests/test_synthesis.py`
- Required cases: prompt shape (paper envelopes present, question present,
  no SYSTEM-role leakage); citation rewriting only expands known ids;
  no-analysis skeleton renders all candidates
- Quick verify: `pnpm test:api -- tests/test_synthesis.py`
- Pass criteria: deterministic outputs given a fake LLM that echoes a
  canned brief; citation expansion is idempotent

## Related Docs
- [docs/features/pdf-pipeline.md](pdf-pipeline.md)
- [docs/features/briefing-archive.md](briefing-archive.md)
- [docs/SECURITY.md](../SECURITY.md) — prompt-injection envelopes
