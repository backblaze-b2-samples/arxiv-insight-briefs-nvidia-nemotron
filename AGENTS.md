<!-- last_verified: 2026-05-26 -->
# AGENTS.md

This is the authoritative control surface for all coding agents on the
`arxiv-insight-briefs` sample. Read this first.

## 1. Repository Map

```
apps/web/          Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
services/api/      FastAPI backend (layered: types/config/repo/service/runtime)
packages/shared/   Shared TypeScript types (mirrors Pydantic models)
docs/              System of record (features, workflows, security, reliability)
docs/exec-plans/   Execution plans and tech debt tracker
```

## 2. Architectural Invariants

**Backend layering**: `types` -> `config` -> `repo` -> `service` -> `runtime`

- No backward imports across layers
- `boto3` only inside `app/repo/`
- `httpx` only inside `app/repo/` (NVIDIA + arxiv PDF download live there)
- `pymupdf` only inside `app/repo/pdf_extractor.py`
- LLM prompt strings only inside `app/service/prompts/`
- No business logic in route handlers (`runtime/`)
- All external APIs wrapped in `repo/` adapters
- All request/response data validated at boundary (Pydantic models)
- No shared mutable state across layers (semaphore + metrics counters are
  thread-safe and live in the service layer)

**Frontend**: shadcn/ui components in `src/components/ui/` are generated —
never modify them.

**Data fetching**: every API call flows through TanStack Query hooks in
`apps/web/src/lib/queries.ts`. No bare `useEffect + fetch` patterns. New
endpoints touch three files: `runtime/<router>.py`, `lib/api-client.ts`,
`lib/queries.ts`.

## 3. Quality Expectations

- **DRY** — do not duplicate logic, types, or constants. Extract shared code
  only when used in 2+ places.
- Structured JSON logging only — no `print()` statements
- No raw SDK calls outside `repo/` layer
- Files stay under 300 lines
- Tests added or updated for every behavior change
- Tests are **hermetic** — never hit `build.nvidia.com`, `arxiv.org`, or
  real B2 from the suite; patch `nemotron_client`, `arxiv_client`, and
  `b2_client` at the repo boundary
- Docs updated in same PR as code changes
- Lint clean before merge
- Prefer boring, composable libraries over clever abstractions

## 4. Mechanical Enforcement

| Rule | Enforced by |
|------|-------------|
| No backward imports | `tests/test_structure.py::test_no_backward_imports` |
| No boto3 outside repo/ | `tests/test_structure.py::test_boto3_only_in_repo` |
| File size < 300 lines | `tests/test_structure.py::test_file_size_limits` |
| All layers exist | `tests/test_structure.py::test_all_layers_exist` |
| No bare print() | `ruff` rule T20 |
| Import ordering | `ruff` rule I001 |
| Frontend strict equality | `eslint` rule eqeqeq |
| No unused vars | `eslint` + `ruff` rules |

## 5. Commands

```bash
# Run
pnpm dev               # start both frontend and backend (preflight via doctor)
pnpm dev:web           # frontend only
pnpm dev:api           # backend only

# Test & Lint
pnpm lint              # frontend lint (eslint)
pnpm build             # frontend type check + build
pnpm lint:api          # backend lint (ruff)
pnpm test:api          # backend tests (pytest, fully offline)
pnpm check:structure   # structural boundary tests
pnpm test:e2e          # Playwright e2e tests
```

## 6. Agent Workflow

1. Read this file first.
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) before structural changes.
3. Read the relevant `docs/features/*.md` before changing a feature.
4. For non-trivial changes, create a plan in `docs/exec-plans/active/`.
5. Implement the smallest coherent change.
6. Run: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
7. Update docs in the same PR (see §8).
8. Move completed plans to `docs/exec-plans/completed/`.
9. Only change files relevant to the task. No drive-by improvements.

## 7. Frontend Conventions

See [docs/dev-workflows.md](docs/dev-workflows.md) for full details.

## 8. Doc Update Mapping

| Change Type | Update Location |
|-------------|-----------------|
| Topic-router logic | `docs/features/topic-routing.md` |
| Arxiv discovery + ranking | `docs/features/paper-discovery.md` |
| PDF cache + extraction | `docs/features/pdf-pipeline.md` |
| Synthesis prompt + output schema | `docs/features/insight-synthesis.md` |
| Archive + presigned share | `docs/features/briefing-archive.md` |
| User journeys | `docs/app-workflows.md` |
| System layout, deployments | `ARCHITECTURE.md` |
| Dev or testing process | `docs/dev-workflows.md` |
| Setup or scope changes | `README.md` |
| Security changes | `docs/SECURITY.md` |
| Reliability changes | `docs/RELIABILITY.md` |
| Active work plans | `docs/exec-plans/active/` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |

If documentation and implementation conflict, update docs in the same PR.
Documentation rot destroys agent reliability.

## 9. Doc Map

| Topic | Location |
|-------|----------|
| System layout, data flows, boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Feature docs | [docs/features/](docs/features/) |
| User journeys | [docs/app-workflows.md](docs/app-workflows.md) |
| Engineering workflows and testing | [docs/dev-workflows.md](docs/dev-workflows.md) |
| Security principles | [docs/SECURITY.md](docs/SECURITY.md) |
| Reliability expectations | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Execution plans | [docs/exec-plans/](docs/exec-plans/) |
| Tech debt | [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) |

## 10. When Unsure

- Prefer boring, stable libraries
- Prefer small PRs over large changes
- Add tests with every change
- Never bypass lint rules without explicit instruction
- Ask before making destructive or irreversible changes
- Never let a user-supplied or arxiv-supplied string into a `system` role
