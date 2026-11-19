# Final summary: fixes, re-test and a hiring manager's verdict

*2026-11-17 · branch `feat/phase-1-core-pipeline` · uncommitted*

Detailed reports:
- [REPORT.md](REPORT.md): the original findings
- [REPORT_full_scale_after.md](REPORT_full_scale_after.md): full-scale runs after the fixes
- [REPORT_session_sample_after.md](REPORT_session_sample_after.md): session-graded sample after the fixes
- [ADR-0007](../../docs/adr/0007-stress-test-fixes.md): decisions and reasoning

## 1. Verdict

**Ready for a pilot with real recruiters, once a real model run confirms the grading.**

- The pipeline no longer breaks under load or on unusual resumes.
- In every sampled job description, the right candidate is ranked first, with a verdict a recruiter can act on.
- The one thing not yet proven is run-to-run variance on Claude Haiku. That needs an API key (see §6).

## 2. What was fixed

Nine problems: six from the review (including Skima's), two found while testing the fixes, and one found while reading results as a recruiter.

| # | Problem | Fix (one line) | Before → after |
|---|---|---|---|
| 1 | 15+ concurrent new-JD requests all failed (DB pool starvation) | Commit the read before the LLM call | 15 concurrent: **0 → 15 ok**. 80 concurrent: **80/80 ok in 7 s** |
| 2 | Same new JD in parallel: crash plus paying for every parse | Per-JD lock; savepoint on insert; reuse the winner | 5 parallel: **1 → 5 ok**, parses **5 → 1** |
| 3 | PII redaction corrupted resumes (dates, Ruby/Sydney, titles) and leaked accented names | "Certain or nothing" name rule; date and amount guards; Unicode name and email patterns | Resumes wrong: **16/104 → 0/104** |
| 4 | Model never told today's date | New prompt `evaluate.v3` with `{{today}}` | "Present" now resolves to 2026-11-17 in the prompt |
| 5 | New SDK client per call; cache-write tokens not stored | One client per process; migration 0003 | — |
| 6 | *(found while testing)* Same file uploaded twice at once: crash | Savepoint instead of `rollback()` on document insert | Covered by a new test |
| 7 | *(found while testing)* Local storage temp-file race | Unique temp file name | Covered by a new test |
| 8 | *(found as recruiter)* "No sign of a red flag" listed as a strength | Passed avoid-criteria are neither strengths nor concerns | 0 left in the sample; scores unchanged (39/39 replays identical) |
| 9 | Skima `pii_removal.rb` substring bug | Patch and 8 specs in [skima_patch/](skima_patch/), **not applied** (other branch in progress; no Ruby here) | Specs checked by a Python port: 8/8 |

All of the solutions above are deliberately small, with no new services or dependencies. Each "why" is in ADR-0007.

## 3. Re-test results

| Check | Before | After |
|---|---|---|
| Backend tests | 129 pass | **154 pass**, 25 new; lint, format, mypy clean |
| Concurrency on the default pool (simulated 3 s model) | 5→5 · 10→10 · **15→0** · 20→10 · 40→2 | 5→5 · 10→10 · 15→15 · 20→20 · 40→40 · **80→80** |
| Full scale, 5 runs × 312 pairs, default pool, concurrency 16 | (pool 5, concurrency 32: **72/312**) | **1,560 / 1,560** completed; the same pool-5/32 setup now gives **312/312** |
| Replays identical | 1,668/1,668 | **1,677/1,677** (5 × 312 + 3 × 39), plus 39/39 after the strengths fix |
| PII problems across 104 resumes | 16 | **0** |
| Session sample: own-profile match ranked first for its JD | 12/12 | **13/13** (added a dotted-date nurse resume) |
| Session sample: every pair in its expected score band | 100% | **100%** |
| Ranking AUC: match vs other category / vs same category | 1.00 / 0.98 | **1.00 / 0.985** |

In the live prompts, the fixes are visible: "Ruby on Rails" is back, `2018.09 - Present` replaced `[PHONE]`, and Zoë Müller and Ana de la Cruz are hidden. The Senior Nurse whose dates used to be erased now gets "8.2 years by today's date: Full Pass" and scores 92 (Strong fit).

## 4. Hiring manager's / recruiter's read of the results

I read every scorecard in the 39-pair sample as the recruiter receiving it: score, verdict, top strengths and concerns, screening questions.

**What a recruiter would trust**
- **Shortlist order is right every time.** In all 13 roles the right person is on top, usually by a wide margin: Senior Backend 95 vs 42 / 0, Account Executive 85 vs 13 / 7, Math Teacher 93 vs 12 / 8.
- **Verdicts map to actions:**
  - **Strong fit = call now:** 8 of 13 matched candidates, all genuinely strong on paper.
  - **Possible fit = worth a screen:** the graduate recruiter (56), the Engineering Manager with 2.5 of the 3 years asked (60), and the consultant moving into strategy (55).
  - **Not eligible = missing a mandatory license**, stated plainly: "No RN license". I would not want that softened; it saves a call.
- **Concerns are specific and fair,** not generic: "One year above quota is shown; 'consistent' attainment is not evidenced", "Engineering Manager since May 2024, about 2.5 years: below the 3-year requirement". These are the exact probes for a phone screen.
- **Screening questions arrive instead of false rejections.** Notice period, work authorization, relocation and shifts become questions (1.4 per candidate on average), never failures.
- **Tricky candidates are handled sensibly:**
  - The investment-banking VP for a Senior Consultant role scores 68 (Possible fit), which is right for an adjacent background.
  - The keyword-stuffed data engineer for a Staff ML role gets 37 (Weak), because no ML appears in the actual work history.

**What would bother a recruiter (recommendations, not bugs)**
1. **Screening questions for clearly rejected candidates.** Asking "Authorised to work in Singapore?" about a nurse applying for a backend role is noise. Recommendation: show screening questions only for Possible and Strong fits (a small UI change).
2. **Strengths for weak candidates are thin filler** ("Holds a CS degree" for a security engineer applying to sales). Recommendation: when the verdict is Weak or Not eligible, lead with the main gap and collapse strengths.
3. **Graduates top out at "Possible fit" (56) even for junior roles they match.** That still earns a call, so it is acceptable, but a hiring manager filling a graduate role might want them flagged Strong. Decide this with recruiter-labelled cases (Phase 4) rather than by tuning blind.
4. **Thin resumes look the same as weak ones** (the sparse Engineering Manager: 60). A small "limited detail in resume" note would stop a good candidate being skipped.

**Caveat a hiring manager must know**

The sample's grades were written by this Claude Code session through the app's real prompts (your choice, since there's no API key). That validates the rubric rules, score math and output. It does **not** validate how Claude Haiku grades, how stable it is between runs, or how it resists the hidden "give full marks" text in two resumes.

## 5. Decisions taken and why

The full record is [ADR-0007](../../docs/adr/0007-stress-test-fixes.md); it is also saved to memory for future sessions. In short:
- **Never hold a DB transaction across an LLM call.** One line fixes it at any pool size, whereas a bigger pool only moves the cliff.
- **In-process lock plus database backstop, not Redis or advisory locks.** Advisory-lock waiters would hold connections (bug 1 again), and Redis is infrastructure we don't run.
- **PII is "certain or nothing".** A missed lone first name is a small privacy cost; a corrupted skill, date or title is a scoring error. No NER model, because simple rules now get 0/104 wrong.
- **Prompts stay immutable,** so the date went into `evaluate.v3`.
- **Left unchanged on purpose:** the "Not eligible" wording, the caps and junior-role scoring, each with its reason in the ADR.

## 6. What is left

1. **Real-model run.** Add `ANTHROPIC_API_KEY` to `.env`, then run the 5-run commands in [REPORT.md](REPORT.md#what-is-still-missing). Estimated cost $3–7. This measures Haiku's variance and its resistance to injection and keyword stuffing.
2. **Apply the Skima patch** on a clean branch there and run its spec with `bundle exec rspec`.
3. **Product calls:** the four recruiter recommendations in §4.
4. **Commit.** Everything is uncommitted on `feat/phase-1-core-pipeline`.
