# ADR-0002: Tech stack

- **Status:** Accepted
- **Date:** 2026-11-13

## Decision

| Concern | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, uv |
| DB | PostgreSQL 16, SQLAlchemy 2 async + Alembic |
| Storage | Local disk (dev) → MinIO/S3 behind a `Storage` interface |
| LLM | LiteLLM SDK behind our own `llm/client.py` + DB cost ledger |
| Frontend | Vite, React 19, TypeScript strict, Tailwind v4 + shadcn/ui, TanStack Query, React Router |
| Dev env | WSL2 + Docker Desktop on Windows; Makefile entry points |
| CI | GitHub Actions: ruff, mypy, pytest (real Postgres), eslint, prettier, tsc, vitest, build |

## Why

- **Python**: best PDF + LLM ecosystem; Pydantic schemas double as LLM structured-output contracts.
- **Postgres only, no vector DB / queue in v1**: comparing one JD to one resume needs neither; fewer moving parts to debug (ADR-0005 in PLAN.md).
- **Vite SPA, not Next.js**: the backend is FastAPI; no server-rendering needed; simplest mental model for frequent UI changes.
- **shadcn/ui**: components live in our repo, so restyling is editing a file, not overriding a library.
- **Generated API types**: backend contract changes surface as TypeScript errors.

## Alternatives considered

- Ruby/Rails (as in Skima): heavier for a small new service, ML/PDF ecosystem weaker.
- Next.js: extra server runtime and routing concepts without a need.
- Streamlit: fast prototype but hard to maintain/restyle as a product UI.
- pgvector / Turbopuffer / Elasticsearch: deferred until we rank many resumes.
