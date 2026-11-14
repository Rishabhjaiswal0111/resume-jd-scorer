"""LLM access layer (Phase 1).

client.py   provider-agnostic calls (LiteLLM), timeouts, retries, schema validation
ledger.py   writes one llm_calls row per attempt: tokens, price snapshot, cost
pricing.py  model_prices lookup by effective date
cache.py    request-hash response cache (hits recorded at $0)

Rule: every LLM call in the codebase goes through client.py so it is metered.
"""
