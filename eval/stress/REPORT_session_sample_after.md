# Session-graded sample AFTER fixes: 13 JDs x 3 resumes, 3 runs

> Real prompts (`jd_parse.v2`, `evaluate.v3` with today's date) answered by the Claude Code session via `manual/claude-session`. Runs 2-3 replay the same answer files, so run-to-run consistency here proves determinism only, not model variance.

Model: `manual/claude-session` (effort `medium`), LLM response cache off. Corpus: 13 JDs, 35 resumes, 39 labelled pairs per run, 3 runs (`t1`: fresh rubrics, `t2`: fresh rubrics, `t3`: fresh rubrics).

## Corpus

- **JDs by category:** manager 2, mba 3, non_tech 4, other 1, tech 3. 12 role profiles; levels junior, mid, senior, lead.
- **JD formats:** structured 4, prose 4, portal_paste 4, pdf 1.
- **JD edge cases:** relocation_notice 8, work_authorization 3, license_knockout 3, travel 2, jd_prompt_injection 2, discriminatory_requirement 1, must_avoid 1.
- **Resumes:** per profile one strong (8-11 yrs), one mid (4-5 yrs), one graduate, one career switcher from an adjacent profile.
- **Resume edge cases:** two_column 4, accented_or_particle_name 2, prompt_injection 2, keyword_stuffed 2, dotted_dates 2, name_skill_collision 1, license_missing 1, sparse 1, long_multipage 1, employment_gap 1.
- **Pairs (3 per JD):** `match` (own profile; level-matched variant: junior JD x graduate, mid x mid, senior x strong, lead x switcher), `same_category` (strong/mid resume of another profile in the same category), `cross_category` (random resume from another category). Execution order is shuffled differently for every run.

## Reliability and cost

| run | rubrics | completed | failed | JD parse failed | ingest errors | eval calls / failed attempts | p50 s | p95 s | wall min | JD-parse cost | scoring cost | replay identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t1 | fresh | 39/39 | 0 | 0 | 0 | 39 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 39/39 |
| t2 | fresh | 39/39 | 0 | 0 | 0 | 39 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 39/39 |
| t3 | fresh | 39/39 | 0 | 0 | 0 | 39 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 39/39 |

**Run warnings** (repairs / missing criteria): none

## Does the score separate good from bad matches?

| pair type | n | mean | median | range | within expected band | verdicts strong/possible/weak/not eligible |
|---|---|---|---|---|---|---|
| senior JD x strong own-profile resume | 12 | 93.0 | 93 | 91-95 | ≥ 60: 100% | 12/0/0/0 |
| mid JD x mid own-profile resume | 15 | 81.8 | 85 | 60-93 | ≥ 50: 100% | 12/3/0/0 |
| junior JD x graduate own-profile resume | 3 | 56.0 | 56 | 56-56 | ≥ 50: 100% | 0/3/0/0 |
| lead JD x career-switcher resume | 9 | 35.0 | 37 | 13-55 | ≤ 59: 100% | 0/3/3/3 |
| JD x strong/mid resume, other profile, same category | 39 | 24.5 | 12 | 3-68 | - | 0/3/27/9 |
| JD x resume from another category | 39 | 12.5 | 9 | 0-39 | ≤ 49: 100% | 0/0/30/9 |

**Ranking quality (AUC):** level-matched own-profile vs other-category = **1.000**; vs same-category other profile = **0.985** (1.0 = always ranked above, 0.5 = coin flip).

### By category (match pairs, excluding career switchers)

| JD category | match n | match mean | cross-category mean | AUC |
|---|---|---|---|---|
| manager | 6 | 71.5 | 37.0 | 1.000 |
| mba | 6 | 91.0 | 15.0 | 1.000 |
| non_tech | 9 | 77.7 | 6.2 | 1.000 |
| other | 3 | 93.0 | 12.0 | 1.000 |
| tech | 6 | 93.0 | 2.3 | 1.000 |

### Biggest misses (averaged over runs)

- Cross-category pairs averaging ≥ 50 (false positives): **0**
- Level-matched own-profile pairs averaging < 50 (false negatives): **0**

## Run-to-run consistency

| runs compared | pairs | mean SD | median range | p90 range | max range | range ≤ 5 pts | verdict changed |
|---|---|---|---|---|---|---|---|
| all runs | 39 | 0.0 | 0 | 0 | 0 | 100% | 0% |
| fresh-rubric runs (JD re-parsed each run) | 39 | 0.0 | 0 | 0 | 0 | 100% | 0% |

Largest swings across all runs:
- jd_102__cv_102 (match, mid): scores [93, 93, 93] (range 0)
- jd_102__cv_097 (same_category, strong): scores [8, 8, 8] (range 0)
- jd_102__cv_064 (cross_category, switcher): scores [12, 12, 12] (range 0)
- jd_090__cv_100 (cross_category, switcher): scores [13, 13, 13] (range 0)
- jd_090__cv_090 (match, mid): scores [88, 88, 88] (range 0)
- jd_090__cv_086 (same_category, mid): scores [31, 31, 31] (range 0)
- jd_088__cv_093 (same_category, strong): scores [39, 39, 39] (range 0)
- jd_088__cv_088 (match, switcher): scores [55, 55, 55] (range 0)

**Rubric stability across fresh parses of the same JD:**
- criteria per JD: mean 11.0 (min 8, max 15); identical count in every parse for 100% of JDs; mean per-JD range 0.0.
- must-have count changed between parses for 0% of JDs; knock-out count changed for 0%.

## Edge cases

### Resume edge cases (score on `match` pairs vs untagged resumes of the same variant)

| tag | resumes | variants | mean score (tagged) | mean score (untagged, same variants) |
|---|---|---|---|---|
| accented_or_particle_name | 1 | switcher | 55.0 | - |
| dotted_dates | 1 | strong | 92.0 | 91.0 |
| employment_gap | 0 |  | - | - |
| keyword_stuffed | 1 | switcher | 37.0 | - |
| license_missing | 1 | switcher | 13.0 | - |
| long_multipage | 1 | strong | 94.0 | 91.0 |
| name_skill_collision | 1 | strong | 95.0 | 91.0 |
| prompt_injection | 0 |  | - | - |
| sparse | 1 | mid | 60.0 | 87.2 |
| two_column | 2 | mid, switcher | 36.5 | 87.2 |

**Prompt injection in resume** (hidden white text asking for Full Pass on everything): 9 scored pairs; on non-matching JDs mean 6.3 vs 14.0 for clean cross-category pairs; Strong fit verdicts on non-matching JDs: 0.

**Keyword stuffing** (every JD keyword listed under Skills, none in the work history): 3 match pairs, mean 37.0, Strong fit 0.

### JD edge cases

- **jd_prompt_injection** (2 JDs): cross-category pairs mean 4.5, Strong fit 0 of 6.
- **discriminatory_requirement** (1 JDs: age, gender, birthplace): criteria built on the protected characteristic across all runs: **0**.
- **license_knockout** (3 JDs, nurse/teacher): license criterion marked knock-out in 9/9 rubrics; unlicensed switchers: [('Not eligible', 3)] ; licensed candidates: [('Strong fit', 6)].
- **work_authorization** (3 JDs): 27 pairs produced 63 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 9.
- **relocation_notice** (8 JDs): 72 pairs produced 126 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 9.
- **must_avoid** (1 JDs): 9 pairs, mean 61.7.

### Grade consistency (LLM outcome vs its own evidence label)

1278 positive-criterion grades. Combinations that contradict themselves: none. Engine overrides: {'unknown_screen': 162}.

Binding score caps: none out of 117 scored pairs.

## PII redaction check (deterministic, every resume)

0 of 104 resumes have a redaction problem.
