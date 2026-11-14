# ADR-0006: Call OpenRouter directly with httpx instead of LiteLLM

- **Status:** Accepted
- **Date:** 2026-11-14

## Context

ADR-0002 planned LiteLLM behind `llm/client.py`. During Phase 1 we tested the pinned LiteLLM release (1.106.6) against a mocked OpenRouter:

- Any request with `tools` crashed with `No module named 'mcp'`: `completion()` imports LiteLLM's MCP proxy code, which needs a package LiteLLM does not declare. The only workaround is a private `_skip_mcp_handler` flag.
- Importing LiteLLM downloads a model-price map from GitHub unless `LITELLM_LOCAL_MODEL_COST_MAP=True` is set.
- It added ~50 transitive packages (boto3, tokenizers, huggingface-hub, ...).

We only need OpenRouter today, and it speaks the OpenAI Chat Completions format with token usage and its own `usage.cost` in the response.

## Decision

`llm/client.py` posts to OpenRouter's `/chat/completions` with httpx: strict `response_format: json_schema`, `provider.require_parameters`, `provider.data_collection`, and our own retry, ledger and cache logic.

## Consequences

- ✅ Small dependency footprint; exact control over usage parsing and cost.
- ✅ Tests inject `httpx.MockTransport`; nothing is patched globally.
- ⚠️ Direct DeepSeek / Gemini / OpenAI endpoints need their own small adapter when we want them (all three are OpenAI-compatible). Everything goes through `llm/client.py`, so swapping back to LiteLLM later stays a local change.

## Update (2026-11-14): Claude as the default

The default model is now `anthropic/claude-haiku-5-5`, called through the official `anthropic` SDK (structured output via `output_config.format`). OpenRouter stays available by setting `LLM_DEFAULT_MODEL=openrouter/...`. Claude responses carry no cost figure, so `provider_reported_cost_usd` is empty for them; reconcile against the Anthropic Console usage page instead.
