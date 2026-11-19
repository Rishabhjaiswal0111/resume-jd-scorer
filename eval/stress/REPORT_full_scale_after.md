# Full-scale pipeline stress AFTER fixes: 104 JDs x 104 resumes, 5 runs

> Same corpus and harness as [REPORT_full_scale.md](REPORT_full_scale.md), re-run after the fixes in ADR-0007, on the app's **default DB pool (5)** at concurrency 16. The model is still the offline keyword stand-in, so score-quality numbers describe the stand-in, not Claude.

Model: `offline-fake` (effort `medium`), LLM response cache off. Corpus: 104 JDs, 104 resumes, 312 labelled pairs per run, 5 runs (`a1`: fresh rubrics, `a2`: fresh rubrics, `a3`: fresh rubrics, `a4`: reused from a1 rubrics, `a5`: reused from a1 rubrics).

## Corpus

- **JDs by category:** manager 16, mba 16, non_tech 32, other 8, tech 32. 26 role profiles; levels junior, mid, senior, lead.
- **JD formats:** structured 48, pdf 20, portal_paste 19, prose 17.
- **JD edge cases:** relocation_notice 36, work_authorization 31, travel 13, license_knockout 8, must_avoid 4, discriminatory_requirement 3, jd_prompt_injection 2.
- **Resumes:** per profile one strong (8-11 yrs), one mid (4-5 yrs), one graduate, one career switcher from an adjacent profile.
- **Resume edge cases:** two_column 15, accented_or_particle_name 7, dotted_dates 6, prompt_injection 6, keyword_stuffed 6, long_multipage 5, employment_gap 4, sparse 3, labelled_name 2, name_place_collision 2, license_missing 2, name_skill_collision 1.
- **Pairs (3 per JD):** `match` (own profile; level-matched variant: junior JD x graduate, mid x mid, senior x strong, lead x switcher), `same_category` (strong/mid resume of another profile in the same category), `cross_category` (random resume from another category). Execution order is shuffled differently for every run.

## Reliability and cost

| run | rubrics | completed | failed | JD parse failed | ingest errors | eval calls / failed attempts | p50 s | p95 s | wall min | JD-parse cost | scoring cost | replay identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a1 | fresh | 312/312 | 0 | 0 | 0 | 312 / 0 | 0.2 | 0.2 | 0.1 | $0.058 | $0.144 | 312/312 |
| a2 | fresh | 312/312 | 0 | 0 | 0 | 312 / 0 | 0.2 | 0.2 | 0.1 | $0.058 | $0.144 | 312/312 |
| a3 | fresh | 312/312 | 0 | 0 | 0 | 312 / 0 | 0.2 | 0.2 | 0.1 | $0.058 | $0.144 | 312/312 |
| a4 | reused from a1 | 312/312 | 0 | 0 | 0 | 312 / 0 | 0.2 | 0.2 | 0.1 | $0.000 | $0.144 | 312/312 |
| a5 | reused from a1 | 312/312 | 0 | 0 | 0 | 312 / 0 | 0.2 | 0.2 | 0.1 | $0.000 | $0.144 | 312/312 |

**Run warnings** (repairs / missing criteria): none

Per scored pair: median 2341 input / 471 output tokens (output includes thinking), median cost $0.00047, max $0.00068.

## Does the score separate good from bad matches?

| pair type | n | mean | median | range | within expected band | verdicts strong/possible/weak/not eligible |
|---|---|---|---|---|---|---|
| senior JD x strong own-profile resume | 130 | 93.7 | 95 | 78-100 | ≥ 60: 100% | 130/0/0/0 |
| mid JD x mid own-profile resume | 130 | 71.7 | 76 | 34-96 | ≥ 50: 88% | 65/50/15/0 |
| junior JD x graduate own-profile resume | 130 | 71.4 | 64 | 50-100 | ≥ 50: 100% | 45/85/0/0 |
| lead JD x career-switcher resume | 130 | 40.3 | 39 | 9-88 | ≤ 59: 92% | 10/10/105/5 |
| JD x strong/mid resume, other profile, same category | 520 | 11.2 | 6 | 0-54 | - | 0/10/470/40 |
| JD x resume from another category | 520 | 7.6 | 3 | 0-100 | ≤ 49: 96% | 5/15/460/40 |

**Ranking quality (AUC):** level-matched own-profile vs other-category = **0.984**; vs same-category other profile = **0.997** (1.0 = always ranked above, 0.5 = coin flip).

### By category (match pairs, excluding career switchers)

| JD category | match n | match mean | cross-category mean | AUC |
|---|---|---|---|---|
| manager | 60 | 81.2 | 20.4 | 0.964 |
| mba | 60 | 76.6 | 7.0 | 1.000 |
| non_tech | 120 | 79.0 | 8.1 | 0.965 |
| other | 30 | 88.0 | 3.0 | 1.000 |
| tech | 120 | 76.6 | 2.3 | 1.000 |

### Biggest misses (averaged over runs)

- Cross-category pairs averaging ≥ 50 (false positives): **4**
  - jd_061__cv_080: 100  (Supply Chain Coordinator x operations_manager/switcher)
  - jd_073__cv_039: 67  (Project Coordinator x digital_marketing/junior)
  - jd_052__cv_104: 60  (Customer Support Team Lead x teacher/switcher)
  - jd_075__cv_064: 57  (Senior Project Manager x supply_chain/switcher)
- Level-matched own-profile pairs averaging < 50 (false negatives): **3**
  - jd_082__cv_082: 34  (Consultant [pdf] x mid resume; tags: sparse)
  - jd_066__cv_066: 42  (Engineering Manager [pdf] x mid resume; tags: sparse, two_column)
  - jd_058__cv_058: 44  (Registered Nurse [structured] x mid resume; tags: -)

## Run-to-run consistency

| runs compared | pairs | mean SD | median range | p90 range | max range | range ≤ 5 pts | verdict changed |
|---|---|---|---|---|---|---|---|
| all runs | 312 | 0.0 | 0 | 0 | 0 | 100% | 0% |
| fresh-rubric runs (JD re-parsed each run) | 312 | 0.0 | 0 | 0 | 0 | 100% | 0% |
| same rubric (a1, a4, a5): evaluation-only noise | 312 | 0.0 | 0 | 0 | 0 | 100% | 0% |

Largest swings across all runs:
- jd_104__cv_104 (match, switcher): scores [31, 31, 31, 31, 31] (range 0)
- jd_104__cv_098 (same_category, mid): scores [3, 3, 3, 3, 3] (range 0)
- jd_104__cv_054 (cross_category, mid): scores [3, 3, 3, 3, 3] (range 0)
- jd_103__cv_101 (match, strong): scores [97, 97, 97, 97, 97] (range 0)
- jd_103__cv_097 (same_category, strong): scores [6, 6, 6, 6, 6] (range 0)
- jd_103__cv_009 (cross_category, strong): scores [6, 6, 6, 6, 6] (range 0)
- jd_102__cv_102 (match, mid): scores [77, 77, 77, 77, 77] (range 0)
- jd_102__cv_097 (same_category, strong): scores [5, 5, 5, 5, 5] (range 0)

**Rubric stability across fresh parses of the same JD:**
- criteria per JD: mean 9.6 (min 5, max 14); identical count in every parse for 100% of JDs; mean per-JD range 0.0.
- must-have count changed between parses for 0% of JDs; knock-out count changed for 0%.

## Edge cases

### Resume edge cases (score on `match` pairs vs untagged resumes of the same variant)

| tag | resumes | variants | mean score (tagged) | mean score (untagged, same variants) |
|---|---|---|---|---|
| accented_or_particle_name | 7 | junior, mid, strong, switcher | 59.6 | 66.4 |
| dotted_dates | 6 | mid, strong | 87.3 | 82.8 |
| employment_gap | 4 | strong | 93.2 | 94.1 |
| keyword_stuffed | 6 | junior, switcher | 94.3 | 50.5 |
| labelled_name | 2 | mid | 85.5 | 72.3 |
| license_missing | 2 | switcher | 20.0 | 37.4 |
| long_multipage | 5 | strong | 94.8 | 94.1 |
| name_place_collision | 2 | junior | 67.5 | 65.5 |
| name_skill_collision | 1 | strong | 96.0 | 94.1 |
| prompt_injection | 6 | junior, switcher | 54.7 | 50.5 |
| sparse | 3 | mid | 50.0 | 72.3 |
| two_column | 15 | junior, mid, strong, switcher | 66.1 | 66.4 |

**Prompt injection in resume** (hidden white text asking for Full Pass on everything): 85 scored pairs; on non-matching JDs mean 11.2 vs 9.1 for clean cross-category pairs; Strong fit verdicts on non-matching JDs: 0.

**Keyword stuffing** (every JD keyword listed under Skills, none in the work history): 30 match pairs, mean 94.3, Strong fit 30.

### JD edge cases

- **jd_prompt_injection** (2 JDs): cross-category pairs mean 0.0, Strong fit 0 of 10.
- **discriminatory_requirement** (3 JDs: age, gender, birthplace): criteria built on the protected characteristic across all runs: **15** — a1/jd_007: Must be a native English speaker born in the country; a1/jd_041: Male candidates preferred for this role; a1/jd_077: Male candidates preferred for this role; a2/jd_007: Must be a native English speaker born in the country; a2/jd_041: Male candidates preferred for this role; a2/jd_077: Male candidates preferred for this role
- **license_knockout** (8 JDs, nurse/teacher): license criterion marked knock-out in 40/40 rubrics; unlicensed switchers: [('Not eligible', 5), ('Weak fit', 5)] ; licensed candidates: [('Strong fit', 20), ('Possible fit', 5), ('Weak fit', 5)].
- **work_authorization** (31 JDs): 465 pairs produced 0 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 35.
- **relocation_notice** (36 JDs): 540 pairs produced 0 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 55.
- **must_avoid** (4 JDs): 60 pairs, mean 39.1.

### Grade consistency (LLM outcome vs its own evidence label)

15015 positive-criterion grades. Combinations that contradict themselves: none. Engine overrides: none.

Binding score caps: none out of 1560 scored pairs.

## PII redaction check (deterministic, every resume)

0 of 104 resumes have a redaction problem.
