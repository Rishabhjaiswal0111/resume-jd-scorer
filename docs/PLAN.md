# JD × Resume Scorer — Project Plan

> **Goal:** Upload a Job Description (PDF) and a Resume (PDF) → get a **score (0–100)**, **pros**, **cons**, and a **per-criterion breakdown**, with the **exact cost of every run** recorded and reconcilable against provider invoices.
>
> **Status:** Draft v1 · 13 Nov 2026 · Owner: _TBD_
> **Design lineage:** Simplified from Skima's V3 scoring (LLM grades criteria → deterministic code computes the score).

---

## Table of contents

1. [Assumptions & open decisions](#1-assumptions--open-decisions)
2. [Core design principles](#2-core-design-principles)
3. [Tech stack (final)](#3-tech-stack-final)
4. [Architecture](#4-architecture)
5. [Repository structure](#5-repository-structure)
6. [Data model](#6-data-model)
7. [Scoring specification](#7-scoring-specification)
8. [Cost ledger specification](#8-cost-ledger-specification)
9. [API specification](#9-api-specification)
10. [Frontend plan (built for frequent UI change)](#10-frontend-plan-built-for-frequent-ui-change)
11. [Production-level engineering standards](#11-production-level-engineering-standards)
12. [Phased delivery plan (ordered subtasks)](#12-phased-delivery-plan-ordered-subtasks)
13. [Cost estimate](#13-cost-estimate)
14. [Risks & mitigations](#14-risks--mitigations)
15. [Decision log (ADRs)](#15-decision-log-adrs)

---

## 1. Assumptions & open decisions

| # | Assumption (taken until told otherwise) | Impact if changed |
|---|---|---|
| A1 | Backend in **Python** | Swap stack section; design stays the same |
| A2 | Starts as an **internal tool** (single team); auth added in Phase 6 | Earlier auth → move Phase 6.1 forward |
| A3 | LLM via **OpenRouter** in dev (one key, many models, per-request cost in response); direct provider keys optional | Only `llm/` adapter config changes |
| A4 | English-language JDs/resumes, mostly text-based PDFs | Scanned PDFs → OCR fallback in Phase 5 |
| A5 | Dev on **Windows + WSL2 (Ubuntu) + Docker Desktop** | — |
| A6 | Weights are **fixed config (versioned)** in v1, not LLM-generated | Simpler, deterministic, easier to tally; LLM-suggested weights can come later |

**Open decisions** (fill in before Phase 1 ends): default model · hosting target (single VM vs managed cloud) · data-retention period for resumes · who can see costs.

---

## 2. Core design principles

1. **LLM grades, code scores.** The LLM only returns per-criterion outcomes (`Full Pass / Partial Pass / Fail`) + evidence. The number is computed by a pure, unit-tested Python function. Same LLM output ⇒ same score, always.
2. **Every run is reproducible.** Store the rendered prompt, raw response, model, params, prompt version, and engine version. A run can be **replayed** (re-score without calling the LLM).
3. **Every cent is in the ledger.** One row per LLM call with provider-reported token usage and a price snapshot. Run cost = sum of its calls. Cache hits are recorded at $0.
4. **Parse once, score many.** JD parsing (rubric generation) is cached by file hash; N resumes against one JD pay for the JD parse once.
5. **Boring infrastructure.** Postgres + files. No queue, vector DB, or microservices until a measured need exists.
6. **Versioned everything.** `prompt_version`, `engine_version` (score math), `rubric.version`, `model_prices.effective_from`.
7. **Frontend is a thin display layer.** No business logic in the UI; it renders what the API returns.

---

## 3. Tech stack (final)

### Backend
| Concern | Choice |
|---|---|
| Language / runtime | Python 3.12, managed by **uv** |
| Web framework | **FastAPI** + **Pydantic v2** |
| Settings | **pydantic-settings** (`.env` → typed config) |
| ORM / migrations | **SQLAlchemy 2.0** (async) + **Alembic** |
| Database | **PostgreSQL 16** |
| PDF text | **pypdfium2** (primary), **pdfplumber** (fallback for odd layouts); OCR/vision fallback in Phase 5 |
| LLM access | **LiteLLM SDK** wrapped by our own `llm/client.py` (provider-agnostic, tool-call / JSON-schema output) |
| File storage | Local disk (dev) → **MinIO / S3** via one `storage` interface |
| Background jobs | None in v1 → **Arq + Redis** in Phase 5 |
| Logging | **structlog** (JSON), every line carries `request_id` / `run_id` |
| Tests | **pytest**, pytest-asyncio, **respx** (HTTP mocks), **testcontainers** (real Postgres in tests) |
| Quality | **ruff** (lint + format), **mypy --strict** on `app/`, **pre-commit** |

### Frontend
| Concern | Choice | Why (maintainability) |
|---|---|---|
| Build | **Vite** + **React 18** + **TypeScript (strict)** | Fast reloads, no server-rendering complexity |
| UI kit | **shadcn/ui** + **Tailwind CSS** | Components are copied into the repo → edit directly, no library fighting |
| Design tokens | CSS variables (`globals.css`) + Tailwind theme | One place to change colours/spacing/fonts |
| Server state | **TanStack Query** (+ Devtools) | Caching, loading/error states, no Redux |
| Routing | **React Router** | Simple, well known |
| Forms | **React Hook Form** + **Zod** | Typed validation, minimal boilerplate |
| API types | **openapi-typescript** generated from FastAPI's OpenAPI | Backend changes surface as TS compile errors |
| Tables | **TanStack Table** (via shadcn data-table) | Runs list, breakdown tables |
| Tests | **Vitest** + Testing Library; **Playwright** smoke e2e | |
| Package manager | **pnpm** | |

### Infra / tooling
Docker Desktop (WSL2 backend) · `docker compose` (Postgres, MinIO, later Redis, optional Langfuse) · `Makefile` (or `justfile`) · GitHub Actions CI.

---

## 4. Architecture

```
┌──────────── Frontend (Vite React) ────────────┐
│ Upload · Run detail · Runs list · Costs · Rubric │
└───────────────────────┬────────────────────────┘
                        │ REST /api/v1 (typed via OpenAPI)
┌───────────────────────▼────────────────────────┐
│ FastAPI  (api/ routers → services/)             │
│                                                 │
│  services/scoring_service.py  (orchestrates)    │
│     │                                           │
│     ├─ pipeline/extract.py        PDF → text    │  (no LLM)
│     ├─ pipeline/pii.py            strip PII     │  (no LLM)
│     ├─ pipeline/jd_parse.py       JD → rubric   │  LLM call #1 (cached per JD hash)
│     ├─ pipeline/evaluate.py       grade criteria│  LLM call #2
│     ├─ pipeline/scoring_math.py   score         │  PURE FUNCTION
│     └─ pipeline/pros_cons.py      pros/cons     │  PURE FUNCTION
│                                                 │
│  llm/client.py → llm/ledger.py → llm_calls row  │  every call metered
│  repositories/  (DB access only)                │
└───────┬───────────────────────────┬─────────────┘
        │                           │
   PostgreSQL                 File storage (disk / MinIO)
   runs, rubrics, ledger      PDFs, extracted text, prompts, raw responses
```

**Run lifecycle (status machine):**
`created → extracting → parsing_jd (skipped if cached) → evaluating → scoring → completed`
Any step → `failed` with an `error_code` (see §11.4).

---

## 5. Repository structure

```
jd-scorer/
├── README.md                    # 5-minute quickstart
├── PLAN.md                      # this file
├── Makefile                     # make dev / test / lint / migrate / eval / gen-api
├── .env.example
├── docker-compose.yml           # postgres, minio (+ redis, langfuse later)
├── .github/workflows/ci.yml
├── docs/
│   ├── adr/                     # 0001-llm-grades-code-scores.md, ...
│   ├── scoring-spec.md          # authoritative score math (mirrors §7)
│   └── runbook.md               # how to debug a bad score / cost mismatch
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py              # app factory, middleware, routers
│   │   ├── core/                # config.py, logging.py, errors.py, ids.py
│   │   ├── api/v1/              # documents.py, rubrics.py, runs.py, costs.py, health.py
│   │   ├── schemas/             # Pydantic request/response + LLM output schemas
│   │   ├── services/            # scoring_service.py, rubric_service.py, cost_service.py
│   │   ├── pipeline/            # extract, pii, jd_parse, evaluate, scoring_math, pros_cons
│   │   ├── llm/                 # client.py, ledger.py, pricing.py, cache.py
│   │   ├── prompts/             # jd_parse.v1.md, evaluate.v1.md (+ PROMPTS.md changelog)
│   │   ├── storage/             # base.py, local.py, s3.py
│   │   ├── db/                  # models.py, session.py
│   │   └── repositories/        # one per aggregate
│   └── tests/
│       ├── unit/                # scoring_math, pros_cons, pricing, pii, extract
│       ├── integration/         # API + real Postgres + mocked LLM
│       └── fixtures/            # sample PDFs, recorded LLM responses
├── frontend/
│   ├── package.json
│   └── src/  (see §10.2)
└── eval/
    ├── cases/                   # <case_id>/{jd.pdf, resume.pdf, expected.yaml}
    └── run_eval.py              # scores all cases, reports drift + cost per model
```

---

## 6. Data model

All tables: `id UUID PK`, `created_at`, `updated_at`. Money in `NUMERIC(12,8)` USD (never float).

### `documents`
| column | type | notes |
|---|---|---|
| kind | enum `jd`/`resume` | |
| original_filename | text | |
| sha256 | char(64) | unique per kind → dedupe |
| storage_key | text | PDF location |
| page_count | int | |
| extractor | text | `pypdfium2` / `pdfplumber` / `ocr` |
| text_storage_key | text | extracted text |
| char_count | int | |
| is_scanned | bool | low text density detected |

### `rubrics`
| column | type | notes |
|---|---|---|
| jd_document_id | FK documents | |
| version | int | increments on edit |
| title, core_requirement, role_summary | text | |
| criteria | jsonb | list of criterion objects (§7.1) |
| prompt_version | text | e.g. `jd_parse.v1` |
| llm_call_id | FK llm_calls | null if user-edited |
| created_by | text | `llm` / user id |

### `scoring_runs`
| column | type | notes |
|---|---|---|
| rubric_id | FK rubrics | |
| resume_document_id | FK documents | |
| status | enum | §4 |
| error_code, error_message | text | |
| score | numeric(5,2) | final |
| breakdown | jsonb | every weight / earned / cap / rescale step |
| pros, cons | jsonb | list of strings with criterion refs |
| role_overlap, core_demonstration | text | LLM holistic assessments |
| model, prompt_version, engine_version | text | |
| llm_cost_usd | numeric | sum of this run's calls |
| rubric_cost_share_usd | numeric | JD-parse cost ÷ runs on that rubric (informational) |
| latency_ms | int | |
| replay_of_run_id | FK self | set when a run is a replay |

### `criterion_evaluations`
`run_id`, `criterion_key`, `operator`, `importance`, `outcome`, `evidence_strength`, `candidate_value`, `reasoning`, `weight`, `earned`, `was_forced_fail` (bool).

### `llm_calls` (cost ledger — see §8)
### `model_prices` (see §8)

### `eval_results`
`eval_batch_id`, `case_id`, `model`, `score`, `expected_min`, `expected_max`, `passed`, `cost_usd`, `latency_ms`.

---

## 7. Scoring specification

> Mirrors `docs/scoring-spec.md`. Any change bumps `ENGINE_VERSION`.

### 7.1 Criterion (produced by JD parse)
```json
{
  "key": "c_backend_python",
  "name": "Backend Python proficiency",
  "attribute": "hard_skills | soft_skills | experience | education | location | other",
  "operator": "must_have | preferred | nice_to_have | must_avoid | may_avoid",
  "importance": "high | normal",
  "values": ["Python", "FastAPI"],
  "source_excerpt": "3+ years building Python APIs"
}
```

### 7.2 Evaluation (produced by evaluate LLM call, tool-call JSON)
```json
{
  "role_overlap":       { "level": "Strong|Moderate|Weak|None", "summary": "≤30 words" },
  "core_requirement":   { "level": "Clear|Partial|Weak|None",   "summary": "≤40 words" },
  "criteria": [
    { "key": "c_backend_python", "candidate_value": "...",
      "evidence_strength": "evidenced|partial_evidence|not_evidenced|contradicted",
      "outcome": "Full Pass|Partial Pass|Fail", "reasoning": "≤40 words, recruiter-facing" }
  ]
}
```
Validation: every rubric key must appear exactly once; unknown keys dropped (logged); missing keys ⇒ retry once, then `Fail` with `reasoning="Not evaluated"` and a warning flag on the run.

### 7.3 Weights (config, `ENGINE_VERSION = "1.0.0"`)
| bucket | weight |
|---|---|
| must_have | 45 |
| preferred | 20 |
| nice_to_have | 5 |
| must_avoid | 10 |
| may_avoid | 0 |
| role_overlap | 10 |
| core_requirement | 10 |
| **total** | **100** |

Within a bucket, weight splits by importance (`high = 2`, `normal = 1`), rounded to 2 dp; rounding drift goes to the first high-importance item.

### 7.4 Algorithm
1. **Force rules:** a `must_have` with evidence `not_evidenced` or `contradicted` ⇒ `Fail` (`was_forced_fail = true`). `must_avoid` passes when the thing is **absent**.
2. **Percentages:** criteria `Full 100 / Partial 50 / Fail 0`; role_overlap `Strong 100 / Moderate 50 / Weak 25 / None 0`; core_requirement `Clear 100 / Partial 50 / Weak 25 / None 0`.
3. `earned = weight × pct / 100` per entry.
4. **Forfeit** empty buckets; `score = Σearned / (100 − forfeited) × 100`.
5. **Caps** (lowest wins): role_overlap / core_requirement `None → 49`, `Weak → 59`, `Moderate|Partial → 79`.
6. **Hard-fail penalty (configurable, default on):** any `high`-importance `must_have` failed ⇒ `−30` (not cumulative).
7. Clamp 0–100, round 2 dp.
8. Every step written to `breakdown` so the UI can show the full arithmetic.

### 7.5 Pros / cons
- `Full Pass` reasoning → pros; `Partial Pass` / `Fail` → cons.
- Holistic summaries → cons if they triggered a cap, else pros.
- Sort by `operator` (must_have first) then importance.

---

## 8. Cost ledger specification

### `llm_calls`
| column | notes |
|---|---|
| run_id / rubric_id | which business object paid for this |
| purpose | `jd_parse` / `evaluate` / `repair` / `eval` |
| provider, model | as billed (e.g. `openrouter`, `deepseek/deepseek-flash`) |
| prompt_version, request_hash | SHA-256 of (model + rendered prompt + params) — also the cache key |
| input_tokens, cached_input_tokens, output_tokens, reasoning_tokens | **from provider `usage`**, never estimated |
| price_input_per_m, price_cached_per_m, price_output_per_m | **snapshot** from `model_prices` at call time |
| cost_usd | computed: tokens × snapshot prices |
| provider_reported_cost_usd | if provider returns it (OpenRouter does) |
| cost_delta_usd | `provider_reported − computed` (generated column) |
| provider_request_id | for invoice tracing |
| cache_hit | true ⇒ cost 0, tokens copied for reference |
| status, error_code, attempt | retries are separate rows (they cost money too) |
| latency_ms | |
| request_key, response_key | storage keys for full prompt / raw response |

### `model_prices`
`provider, model, input_per_m, cached_input_per_m, output_per_m, currency, effective_from, effective_to, source_url`.
A call with **no matching price row fails loudly in dev** and logs `PRICE_MISSING` in prod (cost recorded as NULL, alerting).

### Reconciliation
- `GET /costs/summary?group_by=day|model|purpose` → compare with provider dashboard.
- Daily job (Phase 5): flag days where `|Σcost_delta| > 2%`.
- Invariant test: `scoring_runs.llm_cost_usd == Σ llm_calls.cost_usd WHERE run_id = …`.

---

## 9. API specification

Base `/api/v1`. All responses carry `X-Request-ID`. Errors use one shape:
`{ "error": { "code": "PDF_UNREADABLE", "message": "...", "request_id": "..." } }`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents` | multipart upload; returns document (deduped by hash) |
| GET | `/documents/{id}` | metadata + extracted-text preview |
| POST | `/rubrics` | `{jd_document_id}` → rubric (returns cached if exists) |
| GET | `/rubrics/{id}` | rubric with criteria |
| PUT | `/rubrics/{id}` | edit criteria → new version (Phase 5) |
| POST | `/score` | **one-shot**: multipart `jd` + `resume` → completed run |
| POST | `/runs` | `{rubric_id, resume_document_id}` → run (sync v1; `202` in Phase 5) |
| GET | `/runs` | list, filter by rubric/status/date/model, paginated |
| GET | `/runs/{id}` | full detail: score, breakdown, criteria, pros/cons, calls, cost |
| POST | `/runs/{id}/replay` | recompute score from stored LLM output (no LLM cost) |
| GET | `/runs/{id}/calls` | ledger rows + links to prompt/response |
| GET | `/costs/summary` | totals by day/model/purpose |
| GET/POST | `/model-prices` | view / add price rows |
| GET | `/healthz`, `/readyz` | liveness / DB+storage readiness |

---

## 10. Frontend plan (built for frequent UI change)

### 10.1 Rules that keep it easy to change
1. **Pages compose, features own, ui renders.** `pages/` only arrange feature components. `features/*` never import from each other. `components/ui/` has zero business knowledge.
2. **No business logic in the browser.** Score, pros/cons, cost all come computed from the API.
3. **All server data via TanStack Query hooks** in `features/*/api.ts` (`useRun(id)`, `useRuns(filters)`). Components never call `fetch` directly.
4. **Generated API types** (`pnpm gen:api`) — a backend change breaks the TS build instead of the UI at runtime.
5. **Design tokens only.** Colours/spacing/radii in CSS variables; no hard-coded hex values in components (lint rule).
6. **Small components** (< ~150 lines). Split before it grows.
7. **Copy-in UI kit (shadcn/ui):** to change a button, edit `components/ui/button.tsx` — no library overrides.
8. **Feature flags / layout variants** via a simple `config/ui.ts` so experiments don't need branches.

### 10.2 Structure
```
frontend/src/
├── main.tsx
├── app/            # router.tsx, providers.tsx (QueryClient, Theme), Layout.tsx, ErrorBoundary.tsx
├── pages/          # UploadPage, RunDetailPage, RunsPage, CostsPage, RubricPage, NotFound
├── features/
│   ├── upload/     # components/, hooks/, api.ts
│   ├── run-detail/ # ScoreCard, BreakdownTable, CriteriaList, ProsCons, CostPanel
│   ├── runs/       # RunsTable, RunFilters
│   ├── costs/      # CostSummary, CostChart
│   └── rubric/     # CriteriaEditor (Phase 5)
├── components/ui/  # shadcn components (owned by us)
├── lib/
│   ├── api/        # generated schema.d.ts + client.ts (fetch wrapper, request-id, error mapping)
│   ├── format.ts   # money, dates, percentages
│   └── utils.ts
├── config/ui.ts
└── styles/globals.css   # design tokens
```

### 10.3 Debuggability
- TanStack Query Devtools in dev.
- Every error toast shows the `request_id` (copyable) → grep backend logs.
- Per-page error boundaries (one broken widget doesn't blank the app).
- Source maps on in all builds.
- Run detail page has a **"Debug" tab**: raw prompt, raw response, ledger rows, breakdown JSON.

### 10.4 Screens (v1)
| Screen | Content |
|---|---|
| Upload | Drop JD + resume → progress by status → redirect to run |
| Run detail | Score dial · pros/cons · criteria table (outcome, evidence, reasoning) · score arithmetic · cost panel · Debug tab |
| Runs list | Filter/sort, score, model, cost, status |
| Costs | Totals by day/model/purpose, avg cost per run, delta vs provider |
| Rubric | View criteria for a JD (edit in Phase 5) |

---

## 11. Production-level engineering standards

### 11.1 Code layering (backend)
`api` (HTTP only: parse, validate, map errors) → `services` (orchestration, transactions) → `pipeline` (pure/near-pure steps) / `llm` / `repositories` (SQL only). No layer imports upward. `pipeline/scoring_math.py` and `pros_cons.py` import nothing from DB/HTTP.

### 11.2 Configuration & secrets
- Single `Settings` class; app fails fast on missing required config at startup.
- Secrets only via env vars; `.env` git-ignored; `.env.example` documents every key.
- No secrets in logs (structlog redaction processor for `*key*`, `*token*`, `authorization`).

### 11.3 Logging & tracing
- JSON logs: `ts, level, event, request_id, run_id, step, duration_ms, model, cost_usd`.
- One log line per pipeline step start/end. LLM prompt/response bodies go to **storage**, not logs.
- Optional Langfuse/OpenTelemetry exporter behind a flag.

### 11.4 Error taxonomy
| code | retry? | user message |
|---|---|---|
| `PDF_UNREADABLE` | no | "Couldn't read this PDF" |
| `PDF_SCANNED` | no (v1) | "Scanned PDF, OCR not enabled yet" |
| `LLM_TIMEOUT` / `LLM_RATE_LIMITED` / `LLM_PROVIDER_ERROR` | yes (backoff, max 3) | "Scoring service busy, retrying" |
| `LLM_INVALID_OUTPUT` | 1 repair attempt | "Scoring failed, please retry" |
| `PRICE_MISSING` | n/a | internal alert |
| `RUBRIC_EMPTY` | no | "No criteria found in JD" |

### 11.5 Testing strategy
| level | what | gate |
|---|---|---|
| Unit | scoring_math (table-driven, incl. Skima worked example), pros_cons, pricing, pii, extraction | 95%+ coverage on `pipeline/`, `llm/pricing.py` |
| Integration | API endpoints with real Postgres (testcontainers) + **recorded LLM responses** | all endpoints |
| Contract | LLM output Pydantic schema validates recorded responses for every supported model | per model |
| Eval | `eval/` golden set — score within expected range, cost reported | manual / nightly, not CI-blocking |
| Frontend | Vitest for components with logic; Playwright smoke: upload → result | CI |

**Rule:** CI never calls a real LLM.

### 11.6 Versioning
- `prompts/*.vN.md` are immutable once used in a stored run; new change ⇒ new file + `PROMPTS.md` changelog.
- `ENGINE_VERSION` (semver) bumps on any score-math change; replays record the engine version used.
- DB migrations: forward-only in prod, every migration reviewed, no data-destroying migration without backup step.

### 11.7 Git & CI
- Trunk-based: short-lived branches, PR required, squash merge, Conventional Commits.
- CI: ruff, mypy, pytest (unit + integration), `pnpm lint`, `tsc --noEmit`, vitest, `pnpm gen:api` diff check (types in sync), Playwright smoke, docker build.
- ADR for any decision that's expensive to reverse (`docs/adr/`).

### 11.8 Security & privacy
- Upload limits: PDF only (magic-byte check), ≤ 10 MB, ≤ 20 pages.
- PII stripped before the LLM prompt; original resume stored, access-controlled.
- Prompt-injection guard: resume wrapped in delimited untrusted block + system-prompt rule; outputs schema-validated.
- Retention policy job (configurable days) deletes PDFs/text, keeps anonymized scores + ledger.

---

## 12. Phased delivery plan (ordered subtasks)

> Estimates assume **one developer**. Each phase ends with a demo and its exit criteria met.

### Phase 0 — Foundations & dev environment (2–3 days)
| # | Subtask | Done when |
|---|---|---|
| 0.1 | Install WSL2 + Ubuntu, Docker Desktop (WSL backend), VS Code + WSL extension, git, uv, Node LTS, pnpm | `docker run hello-world` works inside Ubuntu |
| 0.2 | Create repo in `~/code/jd-scorer`, `README`, `.gitignore`, `.editorconfig`, licence | pushed to remote |
| 0.3 | `docker-compose.yml`: Postgres 16 + MinIO with healthchecks & named volumes | `make up` → both healthy |
| 0.4 | Backend skeleton: FastAPI app factory, `Settings`, structlog, request-id middleware, `/healthz` `/readyz` | `make dev` serves health endpoints |
| 0.5 | SQLAlchemy + Alembic wired; first empty migration | `make migrate` runs clean |
| 0.6 | Frontend skeleton: Vite React TS, Tailwind, shadcn init, Router, QueryClient, Layout, ErrorBoundary | blank app with nav renders |
| 0.7 | Tooling: ruff, mypy, pre-commit, ESLint, Prettier, Vitest, pytest configured | `make lint test` green |
| 0.8 | CI pipeline (GitHub Actions) running lint + tests for both apps | first PR green |
| 0.9 | ADR-0001 (LLM grades, code scores), ADR-0002 (stack) | merged |

**Exit:** a new dev clones and runs everything with `make up && make dev` in < 15 min.

### Phase 1 — Core pipeline, CLI only (5–7 days)
| # | Subtask | Done when |
|---|---|---|
| 1.1 | DB models + migration: `documents`, `rubrics`, `scoring_runs`, `criterion_evaluations`, `llm_calls`, `model_prices` | migration applied; seed script for prices |
| 1.2 | `storage/` interface + local-disk implementation | unit tested |
| 1.3 | `pipeline/extract.py`: pypdfium2 → pdfplumber fallback, scanned detection, text normalization | tests on 5+ sample PDFs incl. 2-column resume |
| 1.4 | `pipeline/pii.py`: email/phone/URL regex + name heuristic | unit tests |
| 1.5 | `llm/pricing.py` + `model_prices` lookup by effective date | unit tests incl. price change mid-month |
| 1.6 | `llm/client.py`: LiteLLM wrapper, tool-call/JSON schema output, timeout, retry w/ backoff, response-schema validation | mocked tests |
| 1.7 | `llm/ledger.py`: write `llm_calls` row for every attempt (success, failure, cache hit), store prompt/response to storage | invariant test passes |
| 1.8 | `llm/cache.py`: request-hash cache (DB-backed) | hit records $0 row |
| 1.9 | `prompts/jd_parse.v1.md` + `pipeline/jd_parse.py` → validated rubric | runs on 5 real JDs, criteria look sane |
| 1.10 | `prompts/evaluate.v1.md` + `pipeline/evaluate.py` → validated evaluation (+ 1 repair attempt) | runs on 5 pairs |
| 1.11 | `pipeline/scoring_math.py` per §7 with full breakdown | table-driven tests, 100% branch coverage |
| 1.12 | `pipeline/pros_cons.py` | unit tests |
| 1.13 | `services/scoring_service.py` orchestration + status transitions + error codes | integration test with recorded responses |
| 1.14 | CLI: `python -m app.cli score jd.pdf resume.pdf` → prints score, pros/cons, cost | demo |
| 1.15 | Record LLM responses as fixtures for tests | committed |

**Exit:** CLI scores a real pair; run row + ledger rows in DB; run cost equals Σ ledger; replaying gives identical score.

### Phase 2 — API layer (3–4 days)
| # | Subtask | Done when |
|---|---|---|
| 2.1 | Error model + exception handlers (§11.4), request-id in responses | tests |
| 2.2 | `POST /documents` with upload validation (type, size, pages), dedupe | tests |
| 2.3 | `POST /rubrics`, `GET /rubrics/{id}` | tests |
| 2.4 | `POST /score` (one-shot) and `POST /runs` | integration tests |
| 2.5 | `GET /runs` (pagination, filters), `GET /runs/{id}`, `GET /runs/{id}/calls` | tests |
| 2.6 | `POST /runs/{id}/replay` | replay == original score test |
| 2.7 | `GET /costs/summary`, `GET/POST /model-prices` | tests |
| 2.8 | CORS for local frontend; OpenAPI tags/examples clean | `/docs` usable |
| 2.9 | `make gen-api` → `frontend/src/lib/api/schema.d.ts`; CI diff check | CI fails if stale |

**Exit:** every endpoint covered by integration tests against real Postgres; OpenAPI drives frontend types.

### Phase 3 — Frontend v1 (5–6 days)
| # | Subtask | Done when |
|---|---|---|
| 3.1 | `lib/api/client.ts`: fetch wrapper, error → typed error with request_id | unit tests |
| 3.2 | Design tokens in `globals.css`, theme, base layout & nav | — |
| 3.3 | Upload page: two drop-zones, validation, submit, progress states | Playwright smoke |
| 3.4 | Run detail: ScoreCard, ProsCons, CriteriaTable | renders recorded run |
| 3.5 | Run detail: BreakdownTable (full arithmetic), CostPanel | numbers match API |
| 3.6 | Run detail: Debug tab (prompt, response, ledger rows, JSON) | — |
| 3.7 | Runs list with filters, sort, pagination | — |
| 3.8 | Costs page: summary cards + by-day/model chart | — |
| 3.9 | Rubric view page | — |
| 3.10 | Empty/loading/error states for every page; error toast with request_id | manual QA checklist |

**Exit:** non-developer can upload, read results, and see cost per run without help.

### Phase 4 — Evaluation & model selection (3–4 days)
| # | Subtask | Done when |
|---|---|---|
| 4.1 | Build golden set: 15–30 JD/resume pairs incl. strong, weak, edge cases (career switch, keyword-stuffed, scanned) | `expected.yaml` per case reviewed by a recruiter |
| 4.2 | `eval/run_eval.py --model X`: scores all cases, writes `eval_results` | report printed |
| 4.3 | Compare 3 models (DeepSeek Flash, Gemini 2.5 Flash, GPT-5 mini): accuracy vs expected, variance across 3 repeats, cost, latency | comparison table in `docs/model-choice.md` |
| 4.4 | Prompt tuning loop (new prompt versions, never edit used ones) | pass-rate target met (e.g. ≥ 85%) |
| 4.5 | Choose default model; ADR-0003 | merged |
| 4.6 | Prompt-caching check: stable system-prompt prefix, verify `cached_input_tokens` > 0 where supported | ledger shows cached tokens |

**Exit:** default model chosen on data; documented cost per run and accuracy.

### Phase 5 — Scale & features (5–7 days)
| # | Subtask | Done when |
|---|---|---|
| 5.1 | Redis + Arq worker; `POST /runs` returns `202`; UI polls run status | load test 100 runs |
| 5.2 | Bulk: one JD + many resumes (zip or multi-upload), batch view ranked by score | demo |
| 5.3 | Concurrency limit + provider rate-limit handling | no 429 storms in load test |
| 5.4 | Rubric editing (new version), re-score stale runs | version history visible |
| 5.5 | OCR / vision fallback for scanned PDFs (costed in ledger, purpose `ocr`) | scanned case passes |
| 5.6 | Daily cost reconciliation job + delta alert | alert fires on injected mismatch |
| 5.7 | Optional: provider batch APIs for non-urgent bulk (~50% cheaper) | ledger records batch prices |
| 5.8 | Export: run results to CSV / PDF report | — |

### Phase 6 — Production hardening & deploy (5–7 days)
| # | Subtask | Done when |
|---|---|---|
| 6.1 | Auth (e.g. email magic link / Google SSO via a library), roles: admin / user; costs visible to admin | protected routes |
| 6.2 | Multi-tenant fields (`org_id`) on all tables if needed | — |
| 6.3 | Rate limiting per user, upload quotas, per-org monthly budget cap (ledger-based) | budget cap blocks run |
| 6.4 | S3/GCS storage implementation + encryption at rest; signed URLs | — |
| 6.5 | Production Dockerfiles (multi-stage, non-root), compose/k8s manifests | image scanned |
| 6.6 | Deploy target (single VM + managed Postgres to start), HTTPS, env separation (dev/staging/prod) | staging live |
| 6.7 | Observability: Sentry (BE+FE), uptime check, log retention, dashboards (runs/day, error rate, p95 latency, cost/day) | alerts tested |
| 6.8 | Backups + restore drill; data-retention job | restore verified |
| 6.9 | Security review: dependency audit, OWASP basics, prompt-injection tests | checklist done |
| 6.10 | Runbook: "bad score", "cost mismatch", "provider down", "rotate keys" | `docs/runbook.md` |

**Exit:** staging → prod release with rollback plan; on-call runbook exists.

### Timeline summary
| Phase | Duration | Cumulative |
|---|---|---|
| 0 Foundations | 2–3 d | ~0.5 wk |
| 1 Core pipeline | 5–7 d | ~2 wk |
| 2 API | 3–4 d | ~2.5 wk |
| 3 Frontend | 5–6 d | ~3.5 wk |
| 4 Evaluation | 3–4 d | ~4.5 wk |
| 5 Scale & features | 5–7 d | ~6 wk |
| 6 Production | 5–7 d | ~7.5 wk |

Usable internal MVP after **Phase 4 (~4–5 weeks)**.

---

## 13. Cost estimate

### 13.1 Per run (LLM only)
Assumptions: JD parse ≈ 4k input / 1.5k output tokens (once per JD); evaluation ≈ 7k input / 2k output tokens.

| Model | $/1M in / out | JD parse | One scoring | 1,000 resumes × 1 JD |
|---|---|---|---|---|
| DeepSeek V4.1 Flash (off-peak) | 0.15 / 0.60 | ~$0.0015 | ~$0.0023 | ~$2.30 |
| DeepSeek V4.1 Flash (peak) | 0.30 / 1.20 | ~$0.003 | ~$0.0045 | ~$4.50 |
| Gemini 2.5 Flash | 0.30 / 2.50 | ~$0.005 | ~$0.0071 | ~$7.10 |
| GPT-5 mini | 0.25 / 2.00 | ~$0.004 | ~$0.006–0.009 | ~$6–9 |

Prices as published mid-Nov 2026 — **verify and load into `model_prices` before use**; they change often.
Levers: prompt caching (stable system prefix), batch APIs (~50% off), shorter reasoning output.

### 13.2 Development budget
- LLM spend during development + eval: **~$10–30/month**.
- Local infra: **$0**.

### 13.3 Hosting (Phase 6, rough)
- Small VM (2 vCPU / 4 GB) + managed Postgres + object storage + Sentry free tier: roughly **$30–60/month** at low volume. Confirm against the chosen provider.

---

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM output varies between runs | temperature 0 / seed, criterion-level grading, eval variance check (4.3) |
| Model returns malformed JSON | schema-validated tool calls, 1 repair attempt, recorded as separate ledger row |
| Provider price change breaks tally | price snapshot per call, `model_prices` effective dates, reconciliation job |
| Scanned / weird-layout PDFs | extractor fallback chain, scanned detection, OCR in Phase 5 |
| Bias / compliance (protected attributes) | PII stripping, guardrails in prompt, no inference of gender/age/etc., audit trail |
| Prompt injection in resumes | untrusted-block wrapping, schema validation, test cases in eval set |
| UI churn breaks things | thin UI, generated types, Playwright smoke, copy-in components |
| Scope creep toward Skima's full system | ADRs; add queues/vector search only with measured need |

---

## 15. Decision log (ADRs)

| ADR | Decision | Status |
|---|---|---|
| 0001 | LLM grades criteria; deterministic code computes score | Accepted |
| 0002 | Python/FastAPI + Postgres + Vite React/shadcn stack | Accepted |
| 0003 | Default LLM model | Pending (Phase 4) |
| 0004 | Fixed versioned weights instead of LLM-generated weights | Accepted (v1) |
| 0005 | No queue / vector DB in v1 | Accepted |
