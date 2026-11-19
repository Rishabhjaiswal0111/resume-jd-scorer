# ADR-0007: Fixes from the stress test (concurrency, PII, prompt date)

- **Status:** accepted, 2026-11-17
- **Context:** the stress test in [eval/stress/](../../eval/stress/) (104 JDs × 104 resumes, 5 runs, plus a session-graded sample) found the bugs listed in [eval/stress/REPORT.md](../../eval/stress/REPORT.md).
- **Guiding rule:** the product scores one JD against one resume for a recruiter. The fixes therefore aim for the **smallest change that removes the failure and can be explained in one sentence**. No new infrastructure (no Redis, no queue, no NER model) until the product needs it.

## Decisions

### 1. Never hold a pooled DB connection during an LLM call
- **Bug:** `get_or_create_rubric` kept its read transaction (and so a connection) open while the JD was parsed. The ledger needs a second connection, so 15 concurrent first-time JDs exhausted the default pool of 5 + 10, and every request failed after 30 s.
- **Decision:** commit the read before the LLM call. This is one line, uses no new settings, and works at any pool size: 80 concurrent requests on the default pool now all succeed in 7 s.
- **Rejected:**
  - a bigger pool, because that only moves the cliff
  - a shorter pool timeout, because it fails faster but still fails
- **Rule going forward:** any code path that calls the LLM must not have an open transaction on the request's session.

### 2. One JD parse per JD, using an in-process lock with a database backstop
- **Bug:** parallel requests for the same new JD all parsed it (each one paid), and all but one then crashed on `uq_rubrics_jd_document_id_version`.
- **Decision:**
  - A per-JD `asyncio.Lock` (in a `WeakValueDictionary`, so idle locks disappear) makes concurrent requests in one process wait and reuse the first rubric.
  - Across processes, the existing unique constraint is the backstop: the losing insert rolls back to a **savepoint** and the winner's rubric is reused.
- **Why not a Postgres advisory lock:** a waiter would hold a connection while it waits, which is exactly bug 1. A Redis lock adds infrastructure we don't run.
- **Trade-off:** with several API processes, a rare cross-process race can still pay for two parses. It is correct, just slightly more expensive.

### 3. Savepoints, not `session.rollback()`, for "insert or reuse the winner"
- **Bug, found while testing 2:** uploading the same document twice at once took the `IntegrityError` path. That path called `session.rollback()`, which expires *every* object in the request's session (the run, the JD document), so the next attribute access crashed with `MissingGreenlet`.
- **Decision:** wrap each such insert in `session.begin_nested()`, so a lost race undoes only that insert.

### 4. Local storage writes use a unique temp file
- **Bug, found while testing 2:** concurrent writes of the same key shared one `<key>.tmp` file, so the second rename failed.
- **Decision:** name the temp file `<key>.<uuid>.tmp` and keep the atomic rename. (S3 storage is not affected.)

### 5. PII redaction: be certain or do nothing
- **Bugs:**
  - dotted dates (`2019.01 - 2021.12`) became `[PHONE]`
  - "Ruby on Rails" became `[CANDIDATE] on Rails`
  - accented names and particle names leaked
  - job titles were taken as names
  - Unicode emails were half-redacted
  - spaced numbers (`1 200 000`) became `[PHONE]`
- **Decisions:**
  - **The name is the first meaningful line or nothing.** Headings like "Resume" and a "Name:" label are skipped, and text after `|`, `,` or `·` on that line is cut off. If the first line is not name-like, no name is redacted; the old code guessed further down and erased titles.
  - **Only the full name is replaced** (whole words, any case). A lone first name is kept: it is often also a skill or a place (Ruby, Sydney, Austin), and on its own it is not a direct identifier once the email, phone, URL and full name are gone. This was weighed against privacy: a leftover "Priya" says far less than a corrupted "Ruby on Rails" costs in grading.
  - **Names use Unicode letters,** and lowercase particles are allowed (de, la, van, der, bin, …).
  - **Phones must not be date ranges or grouped amounts:** a range whose parts are `YYYY`, `YYYY.MM` or `MM.YYYY` is a date, and digit groups ending in 3 digits without `+` or `(` are an amount.
  - **The email regex is Unicode-aware.**
- **Rejected:**
  - An NER model (spaCy or similar): a new heavy dependency for a problem that simple rules now solve on the whole corpus (0 of 104 resumes wrong, down from 16).
  - Using a stored candidate name, as Skima does: we have no candidate record. Uploads are anonymous files, so there is no name to compare against.

### 6. Today's date goes into the evaluate prompt (`evaluate.v3`)
- **Bug:** the prompt said "present = today" but never said what today is.
- **Decision:** add `Today's date: {{today}}` in a **new** prompt file, following the immutable-prompt rule. `evaluate_resume(today=...)` lets tests pin the date.
- **Side effect:** cache hits now last one day, which is correct, because the answer depends on the date.

### 7. One Anthropic client per process; store cache-write tokens
- **Decisions:**
  - `LLMClient` creates its SDK client once, the API reuses a single `LLMClient` (`get_llm_client`), and the lifespan closes it.
  - Migration 0003 adds `llm_calls.cache_write_tokens`, so the cost can be recomputed from stored tokens.

### 8. Strengths don't list "red flag absent"
- **Found** while reviewing results as a recruiter: "No sign of a boutique market-research-only background" was listed as a top strength.
- **Decision:** a passed `must_avoid` or `may_avoid` criterion is neither a strength nor a concern. It already counts in the score; a red flag that is *present* is still a concern.

## Considered and deliberately not changed

| Item | Why not |
|---|---|
| "Not eligible" shown for completely unrelated candidates | Reviewed as a recruiter: for a nurse job, "Not eligible: no RN license" is the clearest and most accurate label, even for a marketer. |
| Score caps rarely bind | Not a bug: caps exist for keyword-heavy resumes with weak holistic grades. In normal resumes the criteria already pull the score under the cap. |
| Graduates score ~56 ("Possible fit") on junior JDs | They get a screening call, which is the right action. Raising it needs a `jd_parse` change for junior roles, to be decided with recruiter-labelled data (Phase 4), not guessed. |
| Hide screening questions for Weak / Not eligible candidates | UI and product choice, left as a recommendation. |
| Skima's `pii_removal.rb` | A separate repo on another in-progress branch, and Ruby is not installed here. A tested-by-port patch and spec are in [eval/stress/skima_patch/](../../eval/stress/skima_patch/). |

## Verification
- **Tests:** 154 backend tests pass, 25 of them new. The concurrency tests hang or fail against the old code and pass against the new code.
- **Stress re-runs:** see [eval/stress/FINAL_SUMMARY.md](../../eval/stress/FINAL_SUMMARY.md).
