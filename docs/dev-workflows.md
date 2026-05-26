<!-- last_verified: 2026-05-26 -->
# Dev Workflows

Engineering workflows for this repo.

## New Feature

- [ ] Read `AGENTS.md` and `ARCHITECTURE.md`
- [ ] Read the relevant feature doc in `docs/features/`
- [ ] For non-trivial changes, create a plan in `docs/exec-plans/active/`
- [ ] Implement the smallest coherent change
- [ ] Add or update tests
- [ ] Run: `pnpm typecheck && pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- [ ] Update docs in the same PR (see AGENTS.md §8)
- [ ] Move plan to `docs/exec-plans/completed/` after validation

## Bugfix

- [ ] Add a failing test that reproduces the bug
- [ ] Confirm the test fails
- [ ] Implement the fix
- [ ] Rerun tests until green
- [ ] Update docs if behavior changed

## Refactor

- [ ] Read `ARCHITECTURE.md` — respect layering rules
- [ ] Ensure structural tests still pass: `pnpm check:structure`
- [ ] No behavior changes without updating feature docs

## Documentation Update

- [ ] Update only the canonical location (see AGENTS.md §8 doc update mapping)
- [ ] Never duplicate content — link instead
- [ ] Update `<!-- last_verified: YYYY-MM-DD -->` header

## Pull Request

- [ ] One coherent change per PR
- [ ] Run full lint + test suite before submitting
- [ ] Docs updated in the same PR as code changes
- [ ] Only change files relevant to the task — no drive-by improvements

## Testing

### Test types
- **Unit**: pure logic (service layer) — uses fake LLM + fake B2 fixtures
- **Integration**: HTTP handlers via FastAPI TestClient (`tests/test_briefings_api.py`)
- **Structural**: layering rules, import boundaries (`tests/test_structure.py`)
- **E2E**: Playwright (optional — submit + status-poll smoke)

### Hermetic test rules
- Never hit `build.nvidia.com` from a test — patch `app.repo.nemotron_client.chat_completion`.
- Never hit `arxiv.org` — patch `app.repo.arxiv_client.search` / `download_pdf`.
- Never hit B2 with real credentials — `conftest.py` patches `app.repo.b2_client` for the suite.

### Commands
- Quick (backend): `pnpm test:api`
- Structure: `pnpm check:structure`
- Frontend typecheck: `pnpm typecheck`
- Frontend lint: `pnpm lint`
- Backend lint: `pnpm lint:api`
- Full suite: `pnpm typecheck && pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- E2E: `pnpm test:e2e` (run `pnpm --filter @arxiv-insight-briefs/web exec playwright install chromium` once first)

### When to run
- After behavior change: run the relevant subset
- Before PR: run the full suite

## Frontend Conventions

- Tailwind v4: config via CSS `@theme` blocks, NOT `tailwind.config.ts`
- Colors: OKLch format
- Dark mode: `next-themes` with `@custom-variant dark (&:is(.dark *))`
- Animations: `tw-animate-css` (not `tailwindcss-animate`)
- shadcn/ui components in `src/components/ui/` are generated — never modify them

## Data Fetching

All API reads/writes flow through TanStack Query hooks in
`apps/web/src/lib/queries.ts`. Don't add bare `useEffect + fetch` patterns
to components.

**Read** — use the hooks directly:

```tsx
const { data, isLoading, error, refetch } = useBriefing(id);
const { data: archive } = useBriefings();
```

`useBriefing(id)` auto-polls every 2s while the brief is in-flight and
stops once it reaches a terminal status. Surface errors via
`<ErrorState error={error} onRetry={() => refetch()} />` rather than
silently rendering empty UI.

**Write** — wrap mutations with `useMutation` and invalidate on success:

```tsx
const submit = useSubmitBriefing();
const result = await submit.mutateAsync({ question, time_window_months: 12 });
router.push(`/briefings/${result.brief_id}`);
```

**Add a new endpoint** — three places to touch:
1. `services/api/app/runtime/<router>.py` — FastAPI route
2. `apps/web/src/lib/api-client.ts` — typed fetch wrapper
3. `apps/web/src/lib/queries.ts` — `useQuery` / `useMutation` hook + entry in `qk`

Defaults (in `apps/web/src/lib/query-client.tsx`):
- `staleTime: 30s`
- `retry: 1` for transient errors; never retry 4xx (won't get better)
- `refetchOnWindowFocus`: on (TanStack default)
