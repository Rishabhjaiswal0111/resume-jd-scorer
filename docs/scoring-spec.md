# Scoring spec (engine 1.2.0)

Authoritative description of `backend/app/pipeline/scoring_math.py`. Any change to the math bumps `ENGINE_VERSION`; every run stores the version that scored it, and replays re-score with the current engine.

## Inputs

- **Rubric criteria** (from `jd_parse`): `operator` (must_have / preferred / nice_to_have / must_avoid / may_avoid), `importance` (high / normal), plus since jd_parse.v2:
  - `knockout`: genuine dealbreaker (work authorization, mandatory license, non-negotiable location).
  - `verify_in_screening`: something resumes rarely state (relocation, notice period, salary ...).
  - `group`: shared theme for criteria that test the same underlying experience.
- **Grades** (from `evaluate`): per criterion `evidence_strength` and `outcome`; holistic `role_overlap` and `core_requirement` levels.

## Steps

1. **Final outcome per criterion**
   - `verify_in_screening` + `not_evidenced` → **Unknown** (left out of the score, listed as a screening question).
   - `must_have` + `not_evidenced`/`contradicted` → Fail.
   - `must_avoid` + `not_evidenced`/`contradicted` → Full Pass (the unwanted thing is absent).
   - Otherwise the model's outcome.
2. **Weights**: bucket weights must_have 45, preferred 20, nice_to_have 5, must_avoid 10, may_avoid 0, role_overlap 10, core_requirement 10. Within a bucket the weight is split over its *scorable* (non-Unknown) criteria by importance (high = 2, normal = 1), rounded to 2 dp, drift to the first high item.
3. **Earned** = weight × (Full 100 / Partial 50 / Fail 0) %. Holistic: role_overlap Strong 100 / Moderate 50 / Weak 25 / None 0; core_requirement Clear 100 / Partial 50 / Weak 25 / None 0.
4. **Group relief**: for each group with 2+ scorable members, only the single biggest loss counts; the rest of the loss is added back as `group_relief`.
5. **Rescale**: empty buckets (or buckets of only Unknowns) are forfeited; `raw = (criteria earned + group relief + holistic) / (100 − forfeited) × 100`.
6. **Caps** (lowest wins): role_overlap None 49 / Weak 59 / Moderate 79; core_requirement None 49 / Weak 59 / Partial 79; any failed knockout 49.
7. **Optional penalty**: −30 if any high-importance must_have failed. Off by default since 1.1.0 (`SCORING_HARD_FAIL_PENALTY`).
8. **Clamp** to 0–100 and round to a whole number (half up). Since 1.2.0; 1.0/1.1 rounded to 2 dp.
9. **Verdict**: failed knockout → Not eligible; else ≥ 75 Strong fit; ≥ 50 Possible fit; otherwise Weak fit.

Every intermediate value is written to `scoring_runs.breakdown`.

## Changes from 1.0.0

| 1.0.0 | 1.1.0 | Why |
|---|---|---|
| Silent resume on relocation etc. = Fail | Unknown, excluded, asked in screening | Resumes rarely state these; recruiters ask |
| A missing theme counted once per criterion | Counted once per group | One gap (e.g. a domain) shouldn't sink a score several times |
| −30 for any high must_have Fail | Off; knock-outs cap at 49 instead | Separate true dealbreakers from weighted skills |
| Number only | Number + verdict tier | Screeners work in tiers |
