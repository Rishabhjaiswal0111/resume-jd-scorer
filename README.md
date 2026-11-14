# JD × Resume Scorer

Upload a Job Description PDF and a Resume PDF → get a **score (0–100)**, **pros**, **cons**, a **per-criterion breakdown**, and the **exact LLM cost of the run**.

Design rule: **the LLM grades criteria, deterministic code computes the score** (see `docs/adr/0001-llm-grades-code-scores.md`).
Full roadmap: [`docs/PLAN.md`](docs/PLAN.md).

---

## Stack

| Part | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + Alembic, structlog, uv |
| Database | PostgreSQL 16 (Docker) |
| File storage | Local disk in dev, MinIO/S3 later |
| Frontend | Vite, React 19, TypeScript, Tailwind v4 + shadcn/ui, TanStack Query, React Router |
| Tooling | ruff, mypy, pytest, ESLint, Prettier, Vitest, pre-commit, GitHub Actions |

## Quickstart

> **Windows users:** do the one-time setup in [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md) first (WSL2 + Docker Desktop). Run every command below **inside Ubuntu (WSL)**, with the repo in `~/code/jd-scorer`, not on a Windows drive.

```bash
cp .env.example .env          # then fill in API keys when Phase 1 starts
make setup                    # installs backend (uv) + frontend (pnpm) deps + pre-commit
make up                       # starts Postgres in Docker (MinIO is opt-in, see docker-compose.yml)
make migrate                  # applies DB migrations
make dev-api                  # API on http://localhost:8000  (docs at /docs)
make dev-web                  # UI  on http://localhost:5173  (in a second terminal)
```

Open http://localhost:5173 — the header badge shows **API: ok** when the frontend can reach the backend.

## Scoring a JD and a resume

Open http://localhost:5173, add the job description (upload a PDF, or switch to **Paste text** and paste it straight from a job portal), choose the resume PDF and press **Score**. The page shows the score and verdict, pros, cons, screening questions and every criterion with its points and reasoning. LLM cost is admin data: it is kept in the `llm_calls` ledger and shown by the CLI (`make score`), not on the page. The same flow is available from the terminal: `make score jd=JD.pdf resume=RESUME.pdf`.

Which model does the grading is set by `LLM_DEFAULT_MODEL` in `.env`:

| Value | Needs | Cost |
|---|---|---|
| `anthropic/claude-haiku-5-5` (default) | `ANTHROPIC_API_KEY` from console.anthropic.com | ~$0.001-0.003 per resume |
| `openrouter/deepseek/deepseek-v4.1-flash` | `OPENROUTER_API_KEY` | below $0.001 per resume |
| `manual/claude-session` | nothing | $0: each prompt is saved to `backend/var/manual_llm/<hash>.request.md`; write the JSON answer to the matching `.response.json` and press **Retry** |

Run `make seed-prices` once per model so every call's cost can be computed.

## Everyday commands

| Command | What it does |
|---|---|
| `make check` | lint + typecheck + tests for backend and frontend (what CI runs) |
| `make test` | all tests |
| `make lint` / `make format` | lint / auto-format everything |
| `make revision m="add documents table"` | new Alembic migration (autogenerate) |
| `make gen-api` | regenerate frontend API types from the backend's OpenAPI schema |
| `make down` | stop Docker services (data kept in volumes) |
| `make nuke` | stop Docker services **and delete their data** |

## Repository layout

```
backend/   FastAPI app (app/), migrations (alembic/), tests (tests/)
frontend/  Vite React app (src/)
eval/      golden JD/resume pairs for scoring quality checks (Phase 4)
docs/      PLAN.md, ADRs, setup guide
```

## First-run checklist

- [ ] `make setup` succeeded → commit the generated `backend/uv.lock` and `frontend/pnpm-lock.yaml` (CI installs with frozen lockfiles)
- [ ] `make check` is green
- [ ] Push to GitHub and confirm the CI workflow passes

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for code conventions.
