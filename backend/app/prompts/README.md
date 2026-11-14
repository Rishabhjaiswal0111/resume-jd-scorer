# Prompts

- One file per prompt version: `jd_parse.v1.md`, `evaluate.v1.md`, ...
- A prompt file is **immutable once any stored run used it**. To change it, add `*.v2.md`
  and record why in `PROMPTS.md`.
- The prompt version string is stored on every `llm_calls` row and `scoring_runs` row.
