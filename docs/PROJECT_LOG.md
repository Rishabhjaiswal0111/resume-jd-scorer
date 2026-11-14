# Project log: what we built, what we decided, and why

The running history of this project: each major change, the decision behind it, how it was checked, and what was left open. It exists so that anyone (a teammate, a future Claude Code session, or you in six months) can see **why** things are the way they are before changing them.

**Keep it current.** Every major change adds an entry at the top of the timeline: what changed, why, how it was verified, the commit, and any follow-ups. Expensive-to-reverse decisions also get an ADR in [`adr/`](adr/).

Related docs: [PLAN.md](PLAN.md) (roadmap) · [scoring-spec.md](scoring-spec.md) (score math) · [design-system.md](design-system.md) (UI) · [adr/](adr/) (architecture decisions).

## Where things stand (2026-11-14)

- **Working end to end:** a JD (PDF or pasted text) and a resume PDF are turned into a score, verdict, strengths and concerns, screening questions and graded requirements. Results are saved and browsable in History.
- **Branch:** everything is on `feat/phase-1-core-pipeline`; no pull request yet, so CI has not run on it.
- **LLM:** the default model is Claude Haiku 5.5 (`anthropic/claude-haiku-5-5`). The local `.env` uses `manual/claude-session` (a Claude Code session answers the prompts) because there is no API key yet.
- **Tests:** 129 backend + 17 frontend, all passing, stable over repeated runs.

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
- **Demo data:** local History contains test duplicates and a real resume. Clear or seed it before a client demo.
- **Vectors:** not needed for 1 JD × 1 resume scoring. Revisit only if we add search across large resume pools.
