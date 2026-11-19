# Project log: what we built, what we decided, and why

The running history of this project: each major change, the decision behind it, how it was checked, and what was left open. It exists so that anyone (a teammate, a future Claude Code session, or you in six months) can see **why** things are the way they are before changing them.

**Keep it current.** Every major change adds an entry at the top of the timeline: what changed, why, how it was verified, the commit, and any follow-ups. Expensive-to-reverse decisions also get an ADR in [`adr/`](adr/).

Related docs: [PLAN.md](PLAN.md) (roadmap) · [scoring-spec.md](scoring-spec.md) (score math) · [design-system.md](design-system.md) (UI) · [adr/](adr/) (architecture decisions).

## Where things stand (2026-11-19)

- **Working end to end:** sign in (or use the demo account), add jobs (PDF or pasted text, previewed first), drop many resumes on a job and watch them get scored in the background and ranked, open a candidate for the scorecard next to the resume, and search the whole resume database by keywords or pasted text, adding results to a job.
- **Demo:** `make demo` creates `demo@jdscorer.app` / `demo1234` with 3 jobs, 40 synthetic resumes and 10 shortlisted candidates, scored through the real prompts (the local database also has a DevOps job added during testing).
- **Branch:** `feat/phase-1-core-pipeline`; no pull request yet, so CI has not run on it.
- **LLM:** default Claude Haiku 5.5; the local `.env` stays on `manual/claude-session` (this Claude Code session answers prompts).
- **Timing:** every stage stores its duration; `make timings` reports p50/p95/max.
- **Tests:** 167 backend + 14 frontend, plus a Selenium walk-through of every page (desktop and a true 390 px phone viewport).

## Standing rules (how we work)

| Rule | Why |
|---|---|
| Validate with real data; don't assume (APIs, prices, model ids, library behaviour, UI in a real browser) | Several plan assumptions turned out wrong (see 2026-11-14 entries) |
| Prototype first, then harden | Get a working flow in front of people before polishing edge cases |
| Commit + push only main features or important fixes | Meaningful history |
| New dependencies must be released at least 2 weeks ago; pin exact versions | Supply-chain safety |
| Never commit real candidate data (resumes, names, employers) | Privacy; the repo is on GitHub |
| UI follows [design-system.md](design-system.md); recruiter language; no cost or model on user pages | Consistent, client-ready UI; cost is admin data |
| Any score-math change bumps `ENGINE_VERSION`; prompts are immutable once used (new `vN` file instead) | Old runs stay explainable and replayable |

---

## Timeline (newest first)

### 2026-11-19 · Every stage records its time; `make timings`
- **What:** each stage stores how long it took, next to the work it measures (migration **0005**):

  | Stage | Stored in |
  |---|---|
  | Text extraction (PDF or pasted text) | `documents.extraction_ms` |
  | JD parse (model + repair + validation) | `rubrics.parse_ms`; `jobs.parse_queued_at / parse_started_at / parse_finished_at` |
  | Resume scoring, per step (extract, JD parse, redact, evaluate, score, save, total), failed runs included | `scoring_runs.timings` (JSON) and `latency_ms` |
  | Queue: wait for a worker, scoring time, attempts (reset on retry) | `job_candidates.queued_at / started_at / finished_at / attempts` |
  | Every model call | `llm_calls.latency_ms` (manual mode: prompt written → answer file appeared; cache hits: real lookup time) |
  | Every search: query (first 2,000 chars), terms, database size, hits, top match, duration | `search_events` |

  `make timings [days=30]` prints p50 / p95 / max per stage, the slowest extractions and searches, failed runs by reason and retries.
- **Why:** you asked to store the time of everything (extraction, JD parsing, each resume's scoring, search) so you can act on it.
- **Found while doing it:**
  - **All 49 model calls had `latency_ms = 0`:** manual mode hard-coded it. Now real; the old zeros became NULL (unknown, not instant).
  - **Failed runs stored no time:** now they keep the time spent up to the failure.
  - **8 runs stuck in `evaluating` forever:** a worker cancelled mid-run handed its queue row back but never closed the run. Now closed as `CANCELLED`; the 8 old ones were closed as `ABANDONED` by the migration.
  - New `job_candidates` / `jobs` timestamp columns are backfilled from `created_at`; a plain column default would have stamped old rows with the migration time.
- **Checked:** 3 new tests (every stage stored on a full job → score → search flow; a failed run keeps its timings; manual latency = 42.5 s from file times, and a cancelled worker closes its run). Real data through the running app: a new Sales job with 4 new resumes and 5 searches. Extraction is 2–5 ms per one-page PDF; JD parse took 23 s and scoring about 36 s each, both almost all model wait (manual mode = my answer time); with 3 workers the 4th resume waited 59 s in the queue; a pasted-JD search (89 terms) took 331 ms against 18–38 ms for keyword searches; 1 of 5 searches found nothing.
- **Open:** a UI or admin view of these numbers (needs admin auth, PLAN 6.1); alerting on p95 (PLAN 6.7).

### 2026-11-19 · Accounts, Jobs workspace, candidate search, demo account
- **What:** plan in [plan-jobs-and-search.md](plan-jobs-and-search.md).
  - **Accounts:** email + password sign-in, server-side sessions in Postgres (httpOnly cookie, only the token's SHA-256 stored, stdlib `scrypt` passwords). Every API call except health/auth needs a session; each account sees only its own data (another account gets 404).
  - **Jobs:** cards that persist; new job with a live preview (the PDF itself or the pasted text); job page with Candidates / Job description tabs (requirements read from the JD next to the original); multi-resume upload with per-file errors; candidate page with the scorecard next to the resume; remove candidate, delete job, retry.
  - **Background scoring with Postgres as the queue:** rows claimed with `FOR UPDATE SKIP LOCKED` by 3 worker coroutines in the API process; stale claims are re-queued; on shutdown a worker hands its row back at once. Manual mode waits up to 15 min per answer in workers. The UI polls only while something is in progress.
  - **Search:** Postgres full-text search over each account's resumes (generated `tsvector` + GIN). OR-query of the terms, ranked by IDF-weighted share of terms matched; shows matched / missing terms and a highlighted snippet; select results and add them to a job, where they are scored; "Use job's requirements" turns a job into a query; resumes can be uploaded straight to the database.
  - **Demo account:** `make demo` (synthetic `eval/stress` corpus; no real people).
  - **Removed:** the one-shot Score page, History page and `/score`, `/jds`, `/runs` list endpoints (jobs replace them). Migration **0004**.
- **Why:** you asked for a production-like product with a demo account: JDs kept as cards, many candidates per JD with details, and a search that finds the closest resumes and scores them against a job.
- **Decisions:** Postgres sessions over JWT (revocable, no dependency); ownership only on the new tables so documents/rubrics stay deduplicated and cached; Postgres queue over Redis (durable, no new infra; the claim logic moves to Arq later); full-text search over embeddings (no embedding API or key, works in manual mode, explainable "matches 6 of 8 terms").
- **Found and fixed while testing (real browser + real data):**
  - **Search ranked everyone 100 %:** the "matched terms" subquery wasn't correlated, so it compared the query with *all* resumes' words. The Backend job's requirements put a Data Engineer first. Fixed (`.correlate`), with a test that fails on the old code; Ruby Castellanos (scored 97) is now first.
  - **Restart left work stuck for 20 min:** a dev reload (or a deploy) cancelled workers mid-task. Now the claim is handed back on cancel; regression test, and seen live (`claim_released`).
  - **Provisional job title was job-board noise** ("Promoted · Easy Apply · 213 applicants…"): 19 of the corpus's pasted JDs start that way. Now skips portal noise and trims run-on first lines.
  - **Seed skipped two-column resumes** (15 of 104); **names wrapped by two-column PDFs** ("Name: Amara / Petrov") and **headlines cut mid-phrase** are rejoined for display.
  - **Upload loop crashed (MissingGreenlet)** after a bad PDF: `rollback()` expired the user (the ADR-0007 pitfall); now commits instead.
  - **Deleting a job refetched it (404).**
  - Test-harness issues, not app bugs: Chrome's save-password bubble swallowed a click; headless Chrome can't go below 500 px wide, so phone checks now use device emulation at a true 390 px.
- **Checked:** 164 backend tests (12 new API tests incl. account isolation, concurrent workers never taking the same row, shutdown hand-back), 14 frontend tests; Selenium: 41 desktop checks (auth, jobs, tabs, previews, uploads, search, add-to-job, remove, delete, sign-out), live update from Queued to a score without reload, and no horizontal scroll on 8 pages at 390 px. All 17 evaluations and 5 JD parses (demo + testing) were answered in this session through the real prompts; rankings are sensible (e.g. Backend: 97 / 75 / 38 / 38; DevOps: 92 / 87 / 40 / 40 / 30). One demo resume carries a prompt injection; it was ignored and scored 25.
- **Open:** PII redaction still misses names wrapped over two lines by two-column PDFs (first name leaks to the model; the "certain or nothing" rule was left unchanged on purpose). Search can't tell `C++` from `C#`. Sign-up, password reset, teams/roles. Workers should move to their own process for production.

### 2026-11-18 · Manual mode without the Retry button; `make start`; PDFium crash fix (`b233c3e`)
- **What:**
  - **`make start` / `make stop` / `make pending`:** one command starts Docker, Postgres, migrations, the API and the web app, waits until each one actually responds, then opens the browser.
  - **Manual mode no longer shows an error:** the page shows "Waiting for the answer (Step 1 of 2: reading the job description / Step 2 of 2: grading the resume)" and retries by itself, for about 15 min.
  - **The server waits for the answer file:** each request waits up to 20 s (`MANUAL_LLM_WAIT_SECONDS`), so retries don't create a failed run every few seconds.
  - **`scripts/wait-pending.sh`** lets a Claude Code session notice new prompts and answer them.
  - **PDFium extraction is serialised with a lock.**
- **Why:**
  - You keep manual mode and found the Retry error confusing.
  - A new concurrency test showed PDFium segfaults when two uploads extract at the same time. PDFium is not thread-safe, so in production that would crash the whole API process.
- **Checked:**
  - Backend: 156 tests, 3 runs in a row. The new thread test segfaults 3/3 on the old extractor.
  - Frontend: 17 tests.
  - Live: a new score waited 20 s and then returned pending for `jd_parse`; `make start` was ready in 5 s; stop and start worked.

### 2026-11-17 · Fixes from the stress test (`b233c3e`)
- **What:** fixed everything the stress test found, plus three more problems found while fixing and re-testing. Full reasoning: [ADR-0007](adr/0007-stress-test-fixes.md).
  - **No DB transaction during LLM calls:** concurrent new JDs no longer starve the pool.
  - **Per-JD lock and savepoint:** one parse per JD, no unique-constraint crash.
  - **Savepoints on document insert:** a concurrent upload of the same file no longer crashes.
  - **Unique temp files in local storage.**
  - **PII "certain or nothing":** fixes dates, Ruby/Sydney/Austin, title-as-name, Unicode names and emails, and spaced amounts.
  - **`evaluate.v3`** puts today's date in the prompt.
  - **One Anthropic client per process,** and migration **0003** adds `llm_calls.cache_write_tokens`.
  - **Passed avoid-criteria are no longer listed as strengths.**
  - **Skima scrubber:** a patch and spec are in `eval/stress/skima_patch/`, not applied.
- **Why:** you asked for the simplest justifiable fixes, with the decisions remembered. Each fix is the smallest change that removes the failure; no new infrastructure was added.
- **Checked:**
  - Backend: 154 tests (25 new); ruff, format and mypy clean.
  - The concurrency tests fail or hang against the old code.
  - Concurrency on the default pool: 80/80 requests succeed (before: 15 → 0).
  - Same JD in parallel: 5/5 succeed with 1 parse (before: 1/5 and 5 parses).
  - Full scale: 1,560/1,560 pairs completed; the old failing pool-5 setup now gives 312/312 (before: 72/312).
  - PII: 0/104 resumes wrong (before: 16).
  - Session-graded sample: the right candidate is ranked first in 13/13 roles.
  - Summary and recruiter review: [eval/stress/FINAL_SUMMARY.md](../eval/stress/FINAL_SUMMARY.md).
- **Open:**
  - A real Haiku run (needs an API key).
  - The recruiter UI recommendations in FINAL_SUMMARY §4.
  - Applying the Skima patch.
  - Commit.

### 2026-11-17 · Stress test suite and code review (`b233c3e`)
- **What:** `eval/stress/` includes:
  - a deterministic corpus generator: 104 JDs and 104 resume PDFs across tech, non-tech, manager, MBA, design and teaching roles, with edge cases
  - a harness that runs the real `ScoringService` against an isolated `jdscorer_stress` database
  - a concurrency probe
  - a report builder

  Findings are in [eval/stress/REPORT.md](../eval/stress/REPORT.md).
- **Why:** you asked for a full review and a stress test across many role types, with repeated runs.
- **Checked:**
  - 5 full-scale runs (312 pairs each) with an offline keyword stand-in for the model: 1,560/1,560 completed, and every replay was identical.
  - A 36-pair sample run through the real prompts via `manual/claude-session`.
  - 129 backend tests still pass.
- **Found:**
  - DB pool starvation: 15 concurrent first-time requests all fail.
  - A same-JD race: `IntegrityError` on `uq_rubrics_jd_document_id_version`.
  - 6 PII redaction bugs (dotted dates become `[PHONE]`; first names that are also skills or places, such as Ruby or Sydney, are erased; accented names leak; job titles get taken as names). 16 of 104 resumes are affected.
  - The evaluate prompt has no current date.
- **Open:**
  - No real Haiku run yet, because there is no API key, so model run-to-run variance is unmeasured. The commands are in the report.
  - None of the bugs above are fixed yet.

### 2026-11-14 · Client-ready polish (`2e68454`)
- **What:** Inter font, a logo mark, drag-and-drop upload areas, an honest "Analysing the match" state, and a "How it works" strip. The result became a scorecard: a summary with counts, Strengths / Concerns, Questions for the screening call, and requirements grouped by type with colour-coded rating icons. Points, weights and run id moved into a collapsed "Scoring details". The API status shows only when the service is down.
- **Why:** to make the app demoable to clients. The patterns follow hiring scorecards (key takeaways, strengths / concerns, per-attribute colour-coded ratings with evidence, questions for the next round) and clean SaaS UIs (whitespace, one accent colour, Inter). Sources are listed in [design-system.md](design-system.md).
- **Checked:** real-browser screenshots at 1280 px and 390 px of every state. The review caught and fixed three issues: mismatched must-have counts (3/4 vs 3 of 5), red flags reading "0 of 1 met", and the summary sentence repeated as a strength.

### 2026-11-14 · History page and the "Paper & Ink" design system (`eb88aa4`)
- **What:** `GET /api/v1/jds` and `GET /api/v1/runs?jd_document_id=`; a History page grouped by JD; past runs open at `/runs/:id`. Added the theme tokens and shared components, documented in [design-system.md](design-system.md).
- **Why:** you asked to see previous scores per JD, and for a simple, elegant, reusable UI. A single token file plus shared components means a restyle touches one file.
- **Decisions:** replays and failed runs are excluded from History. Runs from before verdicts existed get their tier derived from the score. Cost is never in user-facing responses.

### 2026-11-14 · Mobile-friendly UI (`aa517d4`) and devtools behind a flag (`53667e4`)
- **What:** criteria show as stacked cards on phones, the header fits on one line, and the main button is full width. The TanStack Query devtools button appears only with `VITE_SHOW_QUERY_DEVTOOLS=true`.
- **Why:** phone screenshots showed a broken five-column table. The devtools button confused a non-developer.
- **How checked:** headless Chromium via Playwright. The system libraries it needs were unpacked with `apt-get download` into a scratch folder, because installing them needs root. A "locale" page error found along the way came from the test browser's `en-US@posix` language setting, not from the app.

### 2026-11-14 · Whole-number scores, engine 1.2.0; cost off the page (`577199a`)
- **What:** the final score rounds half up to an integer; the breakdown keeps every exact value. LLM cost, JD-parse share and model were removed from the score page.
- **Why:** you asked for integer scores and said cost is admin data. Rounding happens in the engine, not just the display, so the API, CLI, UI and verdict all agree.
- **Open:** the API still returns cost. Hiding it properly needs admin endpoints with authentication (Phase 6).

### 2026-11-14 · Scoring engine 1.1.0 and prompts v2 (`6fe383c`)
- **What:**
  - **Screening items:** `verify_in_screening` criteria the resume is silent on become "Unknown". They are excluded from the score and listed as screening questions.
  - **Groups:** criteria sharing a `group` lose only their single biggest miss.
  - **Knock-outs:** failed knock-outs cap the score at 49 with the verdict "Not eligible".
  - **Penalty:** the flat −30 penalty is now opt-in.
  - **Verdict tiers:** Strong ≥ 75, Possible ≥ 50, Weak below.
  - **Prompts v2:** must-haves limited to the essentials; partial credit for transferable evidence; about 10 % tolerance on years.
- **Why:** a real Rails JD scored a strong-but-off-domain resume at 17.86. One domain gap was counted five or six times, relocation was failed because resumes rarely mention it, and the −30 penalty dominated. Real screening separates knock-outs, weighted skills and things you simply ask about. Details are in [scoring-spec.md](scoring-spec.md).
- **Re-test (all hand-checked):**

  | Case | Before | After |
  |---|---|---|
  | Backend JD × single-column resume | 90.88 | 90.88 |
  | Backend JD × two-column resume | 55.20 | 59.22 |
  | Data Platform JD (pasted) × two-column | 81.76 | 88.80 |
  | Rails JD × real resume | 17.86 | 59.00 (Possible fit) |

- **Caveat:** Claude Code both wrote these rules and graded the re-test. Grades were changed only where a new rule applied, and prompt examples were made neutral (not taken from the test case). Real calibration still needs Haiku and recruiter-expected scores.

### 2026-11-14 · Paste the JD as text (`175d37e`)
- **What:** `/score` takes either a `jd` PDF or `jd_text` (200+ characters). Pasted text is normalised like PDF text and deduplicated by content. The UI has a PDF / Paste text toggle.
- **Why:** JDs are usually copied from job portals. A realistic paste (bullets, tabs, "Apply now", salary banner) produced a clean rubric that ignored the page noise.

### 2026-11-14 · Score page and scoring API (`1934c63`)
- **What:** `POST /api/v1/score` and `GET /api/v1/runs/{id}`; an upload form and result view. Failed runs return their `run_id`.
- **Why:** you asked to "give the JD and resume and get data" from a UI.
- **Found:** the page once showed blank in the browser. It rendered after restarting Vite with `--force` (fresh dependency bundle) and a hard refresh; the exact cause was not confirmed.

### 2026-11-14 · Keep the phone country code in redaction (`2f405ac`)
- **What:** `+44 7700 900123` becomes `[PHONE +44]`, not `[PHONE]`.
- **Why:** in a real run, redaction removed the resume's only location clue, so every location criterion failed.

### 2026-11-14 · Phase 1 core pipeline, CLI (`4b01038`)
- **What:** data model (migration 0002), PDF extraction, PII redaction, rubric and evaluation prompts (with one repair attempt), pure score math, pros and cons, an LLM client with retries, cache and a per-attempt cost ledger, the scoring service with replay, and a CLI.
- **Decisions, each from something observed:**
  - **Model id:** the plan's default `deepseek/deepseek-flash` does not exist on OpenRouter. The live price of `deepseek-v4.1-flash` also differed from the plan.
  - **LiteLLM dropped ([ADR-0006](adr/0006-direct-openrouter-client.md)):** the pinned version crashed on every structured-output call (an undeclared `mcp` import), downloaded data on import, and added about 50 dependencies.
  - **pypdfium2 first, pdfplumber as fallback:** pdfplumber interleaved the columns of a two-column resume.
  - **PII name detection:** it skips title lines. "Senior Software Engineer" was being removed as a name.
  - **Run foreign keys nullable:** so a run exists from the first step and failures at extraction or JD-parsing are recorded (plan §4).
  - **Test database:** integration tests use a dedicated `<db>_test` database, migrated once and truncated after each test.
- **Claude instead of OpenRouter (same day):** you chose Claude Haiku 5.5. A Claude.ai subscription does not cover API use (that is billed separately in the Anthropic Console), and Haiku's price was verified on Anthropic's live pricing page.
- **Manual provider:** `manual/<name>` writes each prompt to `backend/var/manual_llm/` and waits for an answer file. Driving claude.ai chat from code was refused because it breaks Anthropic's terms. A Claude Code session answering prompts by hand is allowed, and lets the full pipeline run at $0.

### 2026-11-14 · Phase 0 green
- **What:** `make setup / format / up / migrate / check` all pass.
- **Fixes:** `CORS_ORIGINS` JSON-list parsing (a real bug), a deprecated Starlette 422 constant, and MinIO moved behind an opt-in compose profile (you wanted Postgres only).

---

## Open follow-ups

- **Real model:** run with real Haiku (add `ANTHROPIC_API_KEY`) and check that ledger cost matches the Anthropic Console.
- **PR and CI:** open a pull request for `feat/phase-1-core-pipeline` so CI runs.
- **Calibration:** collect 15–30 real JD/resume pairs with recruiter-expected scores (`eval/`, Phase 4) to tune weights and prompts.
- **Points rounding:** per-criterion points are stored at 2 dp, so the scoring-details column can differ from the score by 0.01. Fixing it needs a migration.
- **Cost in API responses:** user-facing responses still include cost; needs admin endpoints and auth (Phase 6).
- **Demo:** use `make demo` (synthetic data). Older one-shot runs remain in the database but are no longer shown anywhere.
- **PII two-column names:** redact names wrapped over two lines (seen on cv_042).
- **Semantic search:** keyword search is live; add embeddings (pgvector) behind the same endpoint if recruiters need synonym matching (React vs Vue).
