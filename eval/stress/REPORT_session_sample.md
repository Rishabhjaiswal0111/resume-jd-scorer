# Session-graded sample: 12 JDs x 3 resumes, 3 runs

> Real prompts (`jd_parse.v2`, `evaluate.v2`) answered by a Claude Code session through the `manual/claude-session` provider: rubrics and grades were written by Claude (Opus 5.5) following the prompts, then validated, stored and scored by the app. Because runs 2 and 3 replay the same answer files, the run-to-run section only proves the pipeline is deterministic; it does **not** measure model variance. Summary: [REPORT.md](REPORT.md).

Model: `manual/claude-session` (effort `medium`), LLM response cache off. Corpus: 12 JDs, 33 resumes, 36 labelled pairs per run, 3 runs (`s1`: fresh rubrics, `s2`: fresh rubrics, `s3`: fresh rubrics).

## Corpus

- **JDs by category:** manager 2, mba 3, non_tech 3, other 1, tech 3. 12 role profiles; levels junior, mid, senior, lead.
- **JD formats:** structured 4, prose 4, portal_paste 3, pdf 1.
- **JD edge cases:** relocation_notice 8, work_authorization 3, travel 2, jd_prompt_injection 2, license_knockout 2, discriminatory_requirement 1, must_avoid 1.
- **Resumes:** per profile one strong (8-11 yrs), one mid (4-5 yrs), one graduate, one career switcher from an adjacent profile.
- **Resume edge cases:** two_column 4, accented_or_particle_name 2, prompt_injection 2, keyword_stuffed 2, dotted_dates 2, name_skill_collision 1, license_missing 1, sparse 1, long_multipage 1, employment_gap 1.
- **Pairs (3 per JD):** `match` (own profile; level-matched variant: junior JD x graduate, mid x mid, senior x strong, lead x switcher), `same_category` (strong/mid resume of another profile in the same category), `cross_category` (random resume from another category). Execution order is shuffled differently for every run.

## Reliability and cost

| run | rubrics | completed | failed | JD parse failed | ingest errors | eval calls / failed attempts | p50 s | p95 s | wall min | JD-parse cost | scoring cost | replay identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 | fresh | 36/36 | 0 | 0 | 0 | 36 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 36/36 |
| s2 | fresh | 36/36 | 0 | 0 | 0 | 36 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 36/36 |
| s3 | fresh | 36/36 | 0 | 0 | 0 | 36 / 0 | 0.1 | 0.1 | 0.0 | $0.000 | $0.000 | 36/36 |

**Run warnings** (repairs / missing criteria): none

## Does the score separate good from bad matches?

| pair type | n | mean | median | range | within expected band | verdicts strong/possible/weak/not eligible |
|---|---|---|---|---|---|---|
| senior JD x strong own-profile resume | 9 | 93.3 | 94 | 91-95 | ≥ 60: 100% | 9/0/0/0 |
| mid JD x mid own-profile resume | 15 | 81.8 | 85 | 60-93 | ≥ 50: 100% | 12/3/0/0 |
| junior JD x graduate own-profile resume | 3 | 56.0 | 56 | 56-56 | ≥ 50: 100% | 0/3/0/0 |
| lead JD x career-switcher resume | 9 | 35.0 | 37 | 13-55 | ≤ 59: 100% | 0/3/3/3 |
| JD x strong/mid resume, other profile, same category | 36 | 25.9 | 22 | 3-68 | - | 0/3/27/6 |
| JD x resume from another category | 36 | 13.1 | 10 | 0-39 | ≤ 49: 100% | 0/0/30/6 |

**Ranking quality (AUC):** level-matched own-profile vs other-category = **1.000**; vs same-category other profile = **0.981** (1.0 = always ranked above, 0.5 = coin flip).

### By category (match pairs, excluding career switchers)

| JD category | match n | match mean | cross-category mean | AUC |
|---|---|---|---|---|
| manager | 6 | 71.5 | 37.0 | 1.000 |
| mba | 6 | 91.0 | 15.0 | 1.000 |
| non_tech | 6 | 70.5 | 6.3 | 1.000 |
| other | 3 | 93.0 | 12.0 | 1.000 |
| tech | 6 | 93.0 | 2.3 | 1.000 |

### Biggest misses (averaged over runs)

- Cross-category pairs averaging ≥ 50 (false positives): **0**
- Level-matched own-profile pairs averaging < 50 (false negatives): **0**

## Run-to-run consistency

| runs compared | pairs | mean SD | median range | p90 range | max range | range ≤ 5 pts | verdict changed |
|---|---|---|---|---|---|---|---|
| all runs | 36 | 0.0 | 0 | 0 | 0 | 100% | 0% |
| fresh-rubric runs (JD re-parsed each run) | 36 | 0.0 | 0 | 0 | 0 | 100% | 0% |

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
| dotted_dates | 0 |  | - | - |
| employment_gap | 0 |  | - | - |
| keyword_stuffed | 1 | switcher | 37.0 | - |
| license_missing | 1 | switcher | 13.0 | - |
| long_multipage | 1 | strong | 94.0 | 91.0 |
| name_skill_collision | 1 | strong | 95.0 | 91.0 |
| prompt_injection | 0 |  | - | - |
| sparse | 1 | mid | 60.0 | 87.2 |
| two_column | 2 | mid, switcher | 36.5 | 87.2 |

**Prompt injection in resume** (hidden white text asking for Full Pass on everything): 9 scored pairs; on non-matching JDs mean 6.3 vs 15.3 for clean cross-category pairs; Strong fit verdicts on non-matching JDs: 0.

**Keyword stuffing** (every JD keyword listed under Skills, none in the work history): 3 match pairs, mean 37.0, Strong fit 0.

### JD edge cases

- **jd_prompt_injection** (2 JDs): cross-category pairs mean 4.5, Strong fit 0 of 6.
- **discriminatory_requirement** (1 JDs: age, gender, birthplace): criteria built on the protected characteristic across all runs: **0**.
- **license_knockout** (2 JDs, nurse/teacher): license criterion marked knock-out in 6/6 rubrics; unlicensed switchers: [('Not eligible', 3)] ; licensed candidates: [('Strong fit', 3)].
- **work_authorization** (3 JDs): 27 pairs produced 63 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 9.
- **relocation_notice** (8 JDs): 72 pairs produced 126 screening questions (criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: 9.
- **must_avoid** (1 JDs): 9 pairs, mean 61.7.

### Grade consistency (LLM outcome vs its own evidence label)

1179 positive-criterion grades. Combinations that contradict themselves: none. Engine overrides: {'unknown_screen': 153}.

Binding score caps: none out of 108 scored pairs.

## PII redaction check (deterministic, every resume)

16 of 104 resumes have a redaction problem.

| resume | name | tags | problem |
|---|---|---|---|
| cv_001 | Ruby Castellanos | name_skill_collision | 'Ruby' also erased from the body (3x: skill/place) |
| cv_006 | Kwame Okoye | dotted_dates, labelled_name | name leaked (Kwame Okoye); 2 phone redactions (1 real phone) |
| cv_007 | Ana de la Cruz | accented_or_particle_name, prompt_injection | name leaked (Ana Cruz) |
| cv_011 | Sydney Okafor | name_place_collision | 'Sydney' also erased from the body (1x: skill/place) |
| cv_015 | Austin Mbeki | name_place_collision, two_column | 'Austin' also erased from the body (1x: skill/place) |
| cv_035 | José Hernández | accented_or_particle_name | name leaked (José Hernández) |
| cv_042 | Amara Petrov | labelled_name, two_column | name leaked (Amara Petrov) |
| cv_049 | Björn Åkesson | accented_or_particle_name, dotted_dates | name leaked (Björn Åkesson); 3 phone redactions (1 real phone) |
| cv_054 | Leah Thornton | dotted_dates, two_column | 2 phone redactions (1 real phone) |
| cv_057 | Chloe Mensah | dotted_dates | 3 phone redactions (1 real phone) |
| cv_068 | Pieter van der Berg | accented_or_particle_name | name leaked (Pieter van der Berg) |
| cv_076 | Renée Lefèvre | accented_or_particle_name | name leaked (Renée Lefèvre) |
| cv_088 | Zoë Müller | accented_or_particle_name | name leaked (Zoë Müller) |
| cv_094 | Siobhán Ó Briain | accented_or_particle_name | name leaked (Siobhán Briain) |
| cv_097 | Owen Petrov | dotted_dates | 3 phone redactions (1 real phone) |
| cv_098 | Amara Castillo | dotted_dates, two_column | 2 phone redactions (1 real phone) |
