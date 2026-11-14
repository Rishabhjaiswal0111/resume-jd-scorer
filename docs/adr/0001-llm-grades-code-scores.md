# ADR-0001: The LLM grades criteria; deterministic code computes the score

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

We need a 0–100 score, pros and cons for a JD/resume pair. Asking an LLM to output the number directly makes scores hard to explain, varies between runs and models, and can't be recalculated when we tune weights. Skima's V3 pipeline moved away from "LLM picks the score" for the same reasons.

## Decision

1. The JD is parsed once into a **rubric**: criteria with an operator (`must_have`, `preferred`, `nice_to_have`, `must_avoid`, `may_avoid`) and importance.
2. The evaluation LLM call returns, per criterion, `outcome` (`Full Pass` / `Partial Pass` / `Fail`), `evidence_strength` and a short reasoning, plus two holistic levels (role overlap, core requirement).
3. A **pure Python function** (`pipeline/scoring_math.py`) turns those outcomes into the score using versioned weights, rescaling, caps and penalties (PLAN.md §7). It records every step in `breakdown`.
4. Pros/cons are derived from criterion reasoning — no extra LLM call.

## Consequences

- ✅ Every score is explainable line by line and reproducible from stored LLM output (replay).
- ✅ Weight/cap tuning doesn't require re-calling the LLM.
- ✅ Models can be compared on criterion-level agreement, not just final numbers.
- ⚠️ Score quality depends on rubric quality; JD parsing needs its own evaluation.
- ⚠️ Changes to the math must bump `ENGINE_VERSION`.
