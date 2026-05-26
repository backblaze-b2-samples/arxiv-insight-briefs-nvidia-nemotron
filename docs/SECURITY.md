<!-- last_verified: 2026-05-26 -->
# Security

Security principles and implementation for the arxiv-insight-briefs sample.

## Threat model

The sample is a single-user research tool. Trust boundaries:

- **Browser → API**: CORS-restricted to configured origins (`api_cors_origins`).
- **API → Backblaze B2**: authenticated via B2 application keys + S3v4 signing.
- **API → NVIDIA Build**: bearer-token auth over HTTPS.
- **API → arxiv.org**: anonymous over HTTPS — arxiv has no auth surface.
- **Browser → B2** (presigned GETs): time-limited tokens; never exposes credentials.

## Secrets handling

- `.env` is gitignored; only `.env.example` ships with the repo.
- B2 application keys and `NVIDIA_API_KEY` are read from environment via
  `pydantic-settings` and never logged. Doctor's preflight refuses to start
  the API if any required B2 var is missing.
- Use a B2 application key scoped to a single bucket with `readFiles`,
  `writeFiles`, and `deleteFiles` permissions. The "clear briefings" action
  needs delete; nothing in the pipeline requires `listKeys` or wider scope.
- Never commit a real `NVIDIA_API_KEY` — the free tier is rate-limited per key.

## Prompt-injection from arxiv content

Treat arxiv abstracts AND extracted PDF text as **untrusted user input**:

- Abstracts and PDF text never enter the `system` role of an LLM call.
- Both are always wrapped in an explicit envelope inside the `user` role:
  `<paper id="…">…</paper>` for synthesis, `<abstracts>…</abstracts>` for
  ranking. The system prompt explicitly instructs the model to ignore any
  instructions embedded inside those tags.
- The user's natural-language question is similarly wrapped in
  `<question>…</question>`. We do not blindly concatenate user text into a
  prompt — the structure is enforced in `app/service/prompts/*.py`.
- Citation rewriting only re-emits arxiv ids the manifest already knows
  about; a model that hallucinates an `[arxiv:HACKER]` token gets left as
  inert text, not turned into a clickable link.

## Presigned URLs

- Per-citation PDF links and the brief-share link are signed GETs with a
  `presigned_ttl_seconds` (default 3600s / 1 hour).
- Generated server-side and embedded directly in the rendered markdown
  — the browser never round-trips through the API for the PDF body.
- B2 honors signature expiry; a leaked link goes stale within the TTL.
- The sample never generates presigned PUTs — all writes go through the API.

## .env discipline

- `.env` is at the repo root and gitignored.
- `services/api/main.py` validates required B2 settings at startup and
  fails fast with an actionable error if anything is missing.
- `scripts/doctor.mjs` mirrors that check before `pnpm dev` and surfaces
  human-readable fixes for each common misconfiguration.

## CORS

- Production deploys must set `api_cors_origins` to the exact frontend
  origin(s). The local default (`localhost:3000`,`localhost:3001`) is a
  development convenience, not a posture.
- `api_cors_origin_regex` is an escape hatch for ephemeral dev origins
  only. Never set it in production.

## DELETE semantics

- `/briefings/{id}?mode=clear` deletes only objects under `briefs/{id}/`.
- The shared PDF cache under `papers/` is intentionally **never touched**
  by the API — it's preserved as a shared resource across briefs.
- The repo-layer guard refuses `delete_prefix("")` or
  `delete_prefix(settings.b2_key_prefix)` so a misconfigured caller cannot
  accidentally empty the sample's bucket prefix.

## What this sample does not protect against

- Multi-tenant data isolation (single-user by design).
- Authenticated API access (no auth middleware shipped — add one before
  exposing the API publicly).
- Long-lived `NVIDIA_API_KEY` rotation. If your key leaks, regenerate it
  in the NVIDIA console — there's no in-app revoke step.
