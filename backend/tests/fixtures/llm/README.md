# LLM response fixtures

Tests never call a real LLM (CONTRIBUTING.md). Files here are the `content` the model
returns, wrapped at test time into an OpenRouter-shaped body by `tests/fakes.py`.

| File | Origin |
|---|---|
| `synthetic_jd_backend.rubric.json` | **Synthetic**: hand-written to match `tests/fixtures/pdfs/jd_backend.pdf` |
| `synthetic_resume_single.evaluation.json` | **Synthetic**: hand-written grading of `resume_single.pdf` against the rubric above |

Real-model responses are stored by the ledger under `var/storage/llm/<call_id>/response.json`;
copy one here (as `recorded/...`) to turn a real run into a fixture.
