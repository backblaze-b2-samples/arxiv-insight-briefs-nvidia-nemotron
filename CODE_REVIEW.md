# Code review checklist — arxiv-insight-briefs

Use this list when reviewing a PR against this sample. Anything marked
**❌** is a blocker; **⚠️** is a discussion item.

## Layering

- ❌ Any `boto3` / `botocore` import outside `app/repo/`
- ❌ Any `httpx` import outside `app/repo/`
- ❌ Any `pymupdf` import outside `app/repo/pdf_extractor.py`
- ❌ Any `arxiv` import outside `app/repo/arxiv_client.py`
- ❌ Any LLM prompt string outside `app/service/prompts/`
- ❌ Any backward import (e.g. `app.service` importing `app.runtime`)
- ❌ Any file over 300 lines

## B2 hygiene

- ❌ S3 client without `customUserAgent` / `user_agent_extra` containing
  `(backblaze-b2-samples)`
- ❌ Hardcoded region string in source (e.g. `"us-west-004"`) outside docs
- ❌ Legacy endpoint/key-id aliases or `AWS_*` prefixes — keys must be exactly `B2_APPLICATION_KEY_ID`,
  `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, `B2_PUBLIC_URL_BASE`
- ❌ `delete_prefix` called with empty string or the sample's top-level prefix
- ⚠️ Any new presigned URL TTL longer than 24 hours

## LLM hygiene

- ❌ Any user-supplied string or arxiv content concatenated into a `system`
  role message
- ❌ Direct `requests` / `urllib` / `openai.Client` calls — must go through
  `nemotron_client.chat_completion`
- ⚠️ Adding a new pipeline LLM stage without documenting its prompt in
  `app/service/prompts/` and adding it to the metrics counters

## Tests

- ❌ Any test that hits the real `build.nvidia.com`, `arxiv.org`, or a
  real B2 endpoint
- ❌ Any new endpoint without a corresponding integration test
- ⚠️ A behavior change without a unit test for the affected service

## Docs

- ❌ Behavior change without an update to the relevant `docs/features/*.md`
- ❌ New env var without an entry in `.env.example`
- ⚠️ Adding to `README.md` instead of the canonical feature doc

## Frontend

- ❌ Direct `fetch` in a component (must go through `lib/queries.ts`)
- ❌ Modifying generated `apps/web/src/components/ui/*` shadcn primitives
- ⚠️ Adding a new TS type that's not mirrored in `packages/shared`
