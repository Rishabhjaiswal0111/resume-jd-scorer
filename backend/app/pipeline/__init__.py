"""Pure / near-pure pipeline steps (Phase 1).

extract.py      PDF -> text (no LLM)
pii.py          strip personal details (no LLM)
jd_parse.py     JD text -> rubric (LLM call #1, cached per JD hash)
evaluate.py     rubric + resume -> per-criterion outcomes (LLM call #2)
scoring_math.py outcomes -> score + breakdown (PURE, no I/O)
pros_cons.py    outcomes -> pros / cons (PURE, no I/O)

Rule: nothing in this package imports from app.api, app.db or app.repositories.
"""
