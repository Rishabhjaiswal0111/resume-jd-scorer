# Plan: accounts, Jobs workspace, candidate search (2026-11-19)

**Status: built and verified on 2026-11-19** (see the PROJECT_LOG entry of that date for what testing found and fixed).

Goal: turn the one-shot "score a pair" page into a product a recruiter can sign in to,
come back to, and work in: a list of jobs, many candidates per job, and a search over
every resume they have uploaded. A demo account shows it with realistic data.

## What the user gets

1. **Sign in** (`/login`), with a "Use the demo account" button. Every page and API call
   needs a session; each account sees only its own jobs and candidates.
2. **Jobs** (`/jobs`): one card per job description, kept across refreshes. Each card shows
   the title, how many candidates are scored / in progress, and the best score.
3. **New job** (`/jobs/new`): upload a PDF or paste text, with a **live preview** of exactly
   what will be added (the PDF itself, or the pasted text). "Add job" creates the card
   and reads the JD in the background.
4. **Job page** (`/jobs/:id`):
   - **Candidates** tab: drop one or many resume PDFs at once. Each becomes a candidate
     card that moves through Queued → Scoring → score, ranked best first.
   - **Job description** tab: the requirements the AI read out of the JD (must-haves,
     nice-to-haves, knock-outs) next to the original document.
5. **Candidate page** (`/jobs/:id/candidates/:cid`): the existing scorecard next to the
   resume itself.
6. **Search** (`/search`): type keywords or paste any text (even a whole JD). It ranks
   every resume in your database by how many of the terms it contains, shows which terms
   matched, and a highlighted snippet. Select results and **Add to job**: they are queued
   and scored against that job like an upload. From a job page, "Find in your database"
   opens search with that job selected and its requirements as the query.
   Resumes can also be uploaded straight into the database from the search page.

The old Score and History pages are replaced: a job with candidates covers both.

## Decisions (and why)

| Decision | Why | Not chosen |
|---|---|---|
| **Email + password, server-side sessions** in Postgres; httpOnly `SameSite=Lax` cookie; password hashed with stdlib `scrypt` | No new dependency, revocable sessions, cookie works through the Vite proxy with no CORS changes | JWT (hard to revoke), OAuth/magic link (needs email/IdP; PLAN 6.1 later) |
| **Ownership on new tables only**: `jobs`, `candidates`, `job_candidates` carry `owner_id`; `documents`, `rubrics`, `scoring_runs` stay content-addressed and shared | Dedup and the rubric cache keep working; access checks happen at the job/candidate level, and runs are reached only through them | `org_id` on every table (PLAN 6.2, not needed yet) |
| **Background scoring with Postgres as the queue**: `jobs.status='pending'` and `job_candidates.status='queued'` rows are claimed with `FOR UPDATE SKIP LOCKED` by N worker coroutines in the API process | Durable across restarts, safe with several processes, no Redis. Uploading 10 resumes returns at once and cards fill in | Redis + Arq (PLAN 5.1; the claim logic moves there unchanged), in-memory queue (lost on restart) |
| Workers use a long manual-mode wait (15 min) | In manual mode each prompt waits for an answer file; one long wait avoids a failed run row every 20 s | Re-queue on every pending (clutters `scoring_runs`) |
| Stale claims (`scoring` for > 20 min) go back to the queue | A crash or restart mid-run doesn't leave a card stuck | Heartbeats (more moving parts) |
| **Search = Postgres full-text search** (`tsvector` + GIN on `candidates`), OR of the query terms, ranked by **share of terms matched**, then `ts_rank_cd` | Works on keywords *and* long pasted text, explainable ("matches 6 of 8 terms"), no new infra, runs offline | Embeddings / pgvector: needs an embedding API or a local model (no key; manual mode can't embed). Can be added behind the same endpoint later |
| Snippets via `ts_headline` with control-character markers, rendered as `<mark>` in React | No HTML from the database reaches `innerHTML` (no XSS through resume text) | Returning HTML |
| Candidate name = the resume's first line when it is a name (same rule PII redaction uses), else the file name | Already battle-tested on 104 resumes; never guesses | NER |
| Demo data from `eval/stress/samples` (synthetic, no real people) | Realistic variety (tech, non-tech, managers), already in the repo | Real resumes |

## Data model (migration 0004)

- `users(id, email unique, name, password_hash, is_demo)`
- `user_sessions(id, user_id, token_hash unique, expires_at)` — the cookie holds a random
  token; only its SHA-256 is stored.
- `jobs(id, owner_id, jd_document_id, title, status pending|parsing|ready|failed, rubric_id,
  error_code, error_message, claimed_at)` — unique `(owner_id, jd_document_id)`: adding the
  same JD twice opens the existing job.
- `candidates(id, owner_id, resume_document_id, name, search_text, search_vector
  GENERATED tsvector)` — unique `(owner_id, resume_document_id)`, GIN index.
- `job_candidates(id, job_id, candidate_id, status queued|scoring|scored|failed, run_id,
  source upload|search, error_code, error_message, claimed_at)` — unique `(job_id, candidate_id)`.

## API (all under `/api/v1`, all but health/auth need a session)

| Method | Path | Does |
|---|---|---|
| POST | `/auth/login`, `/auth/logout`; GET `/auth/me` | sessions |
| GET / POST | `/jobs` | list cards / create from `jd` PDF or `jd_text` |
| GET / DELETE | `/jobs/{id}` | detail with requirements and JD text / delete |
| GET | `/jobs/{id}/document` | the original JD file, for the preview |
| GET / POST | `/jobs/{id}/candidates` | ranked list / upload `resumes[]` |
| POST | `/jobs/{id}/candidates/existing` | add database candidates by id (from search) |
| GET / DELETE | `/jobs/{id}/candidates/{jcid}` | candidate + scorecard / remove from job |
| POST | `/jobs/{id}/candidates/{jcid}/retry` | re-queue a failed one |
| GET / POST | `/candidates` | search (`q`) or list / upload to the database |
| GET | `/candidates/{id}/resume` | the resume PDF, for the preview |
| GET | `/runs/{id}` | only if the run belongs to one of your jobs |

## Steps

1. Migration + models; auth service, `current_user` dependency; demo user CLI.
2. Jobs / candidates services, worker, search; tests (auth isolation, upload → queued →
   scored with the fake LLM, search ranking, add-from-search).
3. Frontend: login + guard, jobs list, new job with preview, job page (tabs, multi-upload,
   polling), candidate page, search page. Shared pieces go into `components/`.
4. `make demo`: demo account with 3 jobs and ~24 resumes; score a few candidates per job
   through the real prompts (manual mode: this session answers them).
5. Selenium walk-through of every page and action at desktop and phone widths; fix what it
   finds; project log, commit.

## Known limits (found while testing)

- `C++` and `C#` both become the term `c` in Postgres' `english` parser, so they can't be searched apart. Numbers are dropped from queries (they match almost every resume).
- Search is lexical: "React" doesn't find "Vue". Semantic search (embeddings) is the next step if needed.
- Workers live in the API process; several API processes are safe (SKIP LOCKED), but a separate worker deployment is the production shape (PLAN 5.1).

## Deferred

Teams/orgs and roles, sign-up and password reset, semantic (embedding) search, rubric
editing, CSV export, rate limits.
