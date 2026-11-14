# Contributing

## Workflow

- Branch from `main`: `feat/…`, `fix/…`, `chore/…`. Keep branches short-lived.
- Commits follow **Conventional Commits**: `feat(scoring): add must_avoid handling`.
- `make check` must pass before opening a PR. CI runs the same checks.
- Squash-merge PRs. Decisions that are expensive to reverse get an ADR in `docs/adr/`.

## Backend rules

| Rule | Why |
|---|---|
| Layers: `api → services → pipeline / llm / repositories`. Never import upward. | Keeps HTTP, orchestration, logic and SQL separable and testable |
| `pipeline/scoring_math.py` and `pipeline/pros_cons.py` do **no I/O** | Scores are reproducible and unit-testable |
| Every LLM call goes through `llm/client.py` | Every call is metered in the `llm_calls` ledger |
| SQL only in `repositories/` | One place to optimise queries |
| Raise `AppError` subclasses with a stable `code`; never return ad-hoc error dicts | One error shape for the frontend |
| Money is `Decimal` / `NUMERIC(12,8)`, never float | Costs must tally exactly |
| Prompts in `app/prompts/*.vN.md` are immutable once used | Old runs stay reproducible |
| Any score-math change bumps `ENGINE_VERSION` | Replays know which math produced a score |
| Log with `get_logger(__name__)` and key-value fields, never f-strings | Searchable JSON logs |
| Never log prompt/response bodies; store them via `storage` | Logs stay small and free of PII |
| Tests never call a real LLM; use recorded responses in `tests/fixtures/` | CI is free, fast and deterministic |

Migrations: `make revision m="…"`, **read the generated file**, then `make migrate`. Prod migrations are forward-only.

## Frontend rules

Look and feel: follow [`docs/design-system.md`](docs/design-system.md) ("Paper & Ink" theme, shared components, mobile-first).

| Rule | Why |
|---|---|
| `pages/` compose features; `features/*` never import each other (ESLint-enforced) | Changing one screen can't break another |
| `components/ui/` is generic and owned by us (shadcn) — edit it directly | No fighting a component library |
| Server data only through TanStack Query hooks in `features/*/api.ts` | Loading/error/caching handled in one way |
| HTTP only through `lib/api/client.ts` (ESLint blocks raw `fetch`) | Every error has a code + request id |
| No business logic in the UI (score, pros/cons, cost come from the API) | UI changes can't change results |
| Colours/spacing via tokens in `styles/globals.css`; no raw hex in components | Restyle in one file |
| Components under ~150 lines; split early | Easy to read and change |
| API types come from `make gen-api`; don't hand-write response types once generated | Backend changes become compile errors |

## Debugging a problem

1. Copy the **request id** from the UI error / `x-request-id` response header.
2. Search backend logs for it — every line of that request carries it.
3. For a scoring question, open the run's **Debug** tab (Phase 3): prompt, raw response, ledger rows, breakdown.
4. To test a score-math fix without paying for the LLM: `POST /api/v1/runs/{id}/replay`.
