"""The ONLY way the app talks to an LLM (CONTRIBUTING.md). Every attempt is metered.

Two providers, picked by the model id prefix:
- `anthropic/<model>`: Claude via the official `anthropic` SDK, structured output via
  `output_config.format` (json_schema). No sampling params (Claude models reject them).
- `openrouter/<model>`: OpenAI-compatible Chat Completions over httpx
  (docs/adr/0006-direct-openrouter-client.md).
- `manual/<name>`: no API. The prompt is written to MANUAL_LLM_DIR/<hash>.request.md and
  the call stops with LLM_RESPONSE_PENDING; a person (or a Claude Code session) writes
  <hash>.response.json and the next run picks it up. Recorded in the ledger at $0.
Tests inject mock transports; nothing is patched globally.

- Output: JSON schema built from a Pydantic model, then re-validated with Pydantic.
  Invalid output => LLM_INVALID_OUTPUT (callers may repair).
- Routing: `provider.require_parameters` so OpenRouter only picks providers that honour
  the schema; `provider.data_collection` (default "deny") keeps resumes out of providers
  that retain prompts.
- Retries: timeouts / 429 / 5xx / connection errors, exponential backoff + jitter, each
  attempt its own ledger row. 4xx other than 429 is not retried.
- Cost: provider `usage` tokens x price snapshot from model_prices; OpenRouter's own
  `usage.cost` is stored alongside for reconciliation.
- Cache: identical request (SHA-256 of the body) => stored response, $0 ledger row.
"""

import asyncio
import contextlib
import copy
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import anthropic
import httpx
import httpx2
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import (
    LLMError,
    LLMInvalidOutputError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMRefusedError,
    LLMRequestRejectedError,
    LLMResponsePendingError,
    LLMTimeoutError,
    PriceMissingError,
)
from app.core.logging import get_logger
from app.llm import cache
from app.llm.ledger import Ledger, LedgerEntry
from app.llm.pricing import PriceSnapshot, Usage, compute_cost, get_price, split_model_id
from app.storage.base import Storage

log = get_logger(__name__)

SUPPORTED_PROVIDERS = ("anthropic", "openrouter", "manual")
_API_KEY_SETTING = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
_MAX_RETRY_AFTER_SECONDS = 30.0
# JSON-schema keywords not reliably supported by strict structured-output providers.
# Constraints are still enforced by Pydantic after the response arrives.
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {"title", "default", "minLength", "maxLength", "pattern", "format", "minItems", "maxItems"}
)


def llm_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic model -> strict-mode JSON schema: refs inlined, every object closed and
    fully required, unsupported keywords removed."""
    schema = model.model_json_schema()
    defs: dict[str, Any] = schema.pop("$defs", {})

    def walk(node: Any, *, is_properties: bool = False) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        if is_properties:  # keys here are field names (e.g. "title"), never keywords
            return {name: walk(sub) for name, sub in node.items()}
        if "$ref" in node:
            return walk(copy.deepcopy(defs[node["$ref"].rsplit("/", 1)[-1]]))
        out = {
            key: walk(value, is_properties=(key == "properties"))
            for key, value in node.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYS
        }
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    result: dict[str, Any] = walk(schema)
    return result


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    value: T
    call_id: UUID
    cost_usd: Decimal | None
    cache_hit: bool
    raw_text: str


@dataclass(frozen=True)
class _Attempt:
    status_code: int | None
    body: dict[str, Any] | None
    error: LLMError | None
    latency_ms: int


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def _usage_from(body: dict[str, Any]) -> Usage | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    if "input_tokens" in usage:  # Anthropic: input_tokens excludes cache reads/writes
        read = int(usage.get("cache_read_input_tokens") or 0)
        write = int(usage.get("cache_creation_input_tokens") or 0)
        details = usage.get("output_tokens_details") or {}
        return Usage(
            input_tokens=int(usage["input_tokens"] or 0) + read + write,
            cached_input_tokens=read,
            output_tokens=int(usage.get("output_tokens") or 0),
            reasoning_tokens=int(details.get("thinking_tokens") or 0),
            cache_write_tokens=write,
        )
    if "prompt_tokens" not in usage:
        return None
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        cached_input_tokens=int(prompt_details.get("cached_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
    )


def _provider_cost(body: dict[str, Any]) -> Decimal | None:
    usage = body.get("usage")
    if not isinstance(usage, dict) or usage.get("cost") is None:
        return None
    try:
        return Decimal(str(usage["cost"]))
    except InvalidOperation:
        return None


def _content_of(body: dict[str, Any]) -> tuple[str, str | None]:
    """-> (answer text, finish reason normalized to stop | length | refusal | ...)."""
    if isinstance(body.get("content"), list):  # Anthropic Message; skip thinking blocks
        text = "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
        stop = body.get("stop_reason")
        return text, {"max_tokens": "length", "end_turn": "stop"}.get(stop or "", stop)
    choices = body.get("choices") or []
    if not choices:
        return "", None
    choice = choices[0]
    message = choice.get("message") or {}
    return str(message.get("content") or ""), choice.get("finish_reason")


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        storage: Storage,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        anthropic_transport: httpx2.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker
        self._storage = storage
        self._ledger = Ledger(sessionmaker)
        self._transport = transport
        self._anthropic_transport = anthropic_transport
        # One SDK client (and connection pool) per LLMClient, created on first use and
        # reused for every call, instead of a new client + TLS handshake per attempt.
        self._anthropic_client: anthropic.AsyncAnthropic | None = None
        self._sleep = sleep

    # ------------------------------------------------------------------ public

    async def complete_json[T: BaseModel](
        self,
        *,
        purpose: str,
        prompt_version: str,
        messages: list[dict[str, str]],
        output_model: type[T],
        schema_name: str,
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        run_id: UUID | None = None,
        rubric_id: UUID | None = None,
    ) -> LLMResult[T]:
        model = model or self._settings.llm_default_model
        provider, provider_model = split_model_id(model)
        if provider not in SUPPORTED_PROVIDERS:
            raise LLMNotConfiguredError(
                f"LLM provider {provider!r} is not supported yet (supported: {SUPPORTED_PROVIDERS})"
            )

        schema = schema or llm_json_schema(output_model)
        if provider in ("anthropic", "manual"):
            body = self._anthropic_body(provider_model, messages, schema)
        else:
            body = self._build_body(provider_model, messages, schema_name, schema)
        req_hash = cache.request_hash(body)
        ctx = {
            "purpose": purpose,
            "provider": provider,
            "model": provider_model,
            "prompt_version": prompt_version,
            "request_hash": req_hash,
            "run_id": run_id,
            "rubric_id": rubric_id,
        }

        if self._settings.llm_cache_enabled:
            hit = await self._try_cache(ctx, output_model)
            if hit is not None:
                return hit

        if provider == "manual":
            return await self._manual(ctx, body, output_model)

        api_key = (
            self._settings.anthropic_api_key
            if provider == "anthropic"
            else self._settings.openrouter_api_key
        )
        if api_key is None or not api_key.get_secret_value():
            raise LLMNotConfiguredError(
                f"{_API_KEY_SETTING[provider]} is not set (see .env.example)"
            )

        price = await self._price_or_raise(provider, provider_model)
        return await self._call_with_retries(
            ctx, body, price, provider, api_key.get_secret_value(), output_model
        )

    # ------------------------------------------------------------------ internals

    def _build_body(
        self,
        provider_model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": provider_model,
            "messages": messages,
            "temperature": self._settings.llm_temperature,
            "seed": self._settings.llm_seed,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "provider": {
                "require_parameters": True,
                "data_collection": self._settings.openrouter_data_collection,
            },
            "usage": {"include": True},
        }

    def _anthropic_body(
        self, provider_model: str, messages: list[dict[str, str]], schema: dict[str, Any]
    ) -> dict[str, Any]:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        return {
            "model": provider_model,
            "max_tokens": self._settings.llm_max_output_tokens,
            "system": system,
            "messages": [m for m in messages if m["role"] != "system"],
            "output_config": {
                "format": {"type": "json_schema", "schema": schema},
                "effort": self._settings.llm_effort,
            },
        }

    def _anthropic(self, api_key: str) -> anthropic.AsyncAnthropic:
        if self._anthropic_client is None:
            http_client = (
                httpx2.AsyncClient(transport=self._anthropic_transport)
                if self._anthropic_transport is not None
                else None
            )
            # max_retries=0: we retry ourselves so every attempt gets its own ledger row.
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=api_key,
                max_retries=0,
                timeout=self._settings.llm_timeout_seconds,
                http_client=http_client,
            )
        return self._anthropic_client

    async def aclose(self) -> None:
        if self._anthropic_client is not None:
            await self._anthropic_client.close()
            self._anthropic_client = None

    async def _send_anthropic(self, body: dict[str, Any], api_key: str) -> _Attempt:
        started = time.perf_counter()

        def done(
            status: int | None, data: dict[str, Any] | None, error: LLMError | None
        ) -> _Attempt:
            return _Attempt(status, data, error, int((time.perf_counter() - started) * 1000))

        try:
            message = await self._anthropic(api_key).messages.create(**body)
        except anthropic.APITimeoutError:
            return done(None, None, LLMTimeoutError("LLM request timed out"))
        except anthropic.APIConnectionError as exc:
            return done(None, None, LLMProviderError(f"LLM connection failed: {exc.message}"))
        except anthropic.RateLimitError as exc:
            error: LLMError = LLMRateLimitedError("LLM provider rate-limited the request")
            if exc.response.headers.get("retry-after"):
                error.details["retry_after"] = exc.response.headers["retry-after"]
            return done(429, None, error)
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:  # incl. 529 overloaded
                return done(
                    exc.status_code,
                    None,
                    LLMProviderError(f"LLM provider error (HTTP {exc.status_code})"),
                )
            return done(
                exc.status_code,
                None,
                LLMRequestRejectedError(
                    f"LLM request rejected (HTTP {exc.status_code}): {exc.message}"
                ),
            )
        return done(200, message.model_dump(mode="json"), None)

    async def _manual[T: BaseModel](
        self, ctx: dict[str, Any], body: dict[str, Any], output_model: type[T]
    ) -> LLMResult[T]:
        folder = self._settings.manual_llm_dir
        stem = folder / ctx["request_hash"]
        answer_path = stem.with_suffix(".response.json")
        if not answer_path.exists() and not stem.with_suffix(".request.md").exists():
            folder.mkdir(parents=True, exist_ok=True)
            parts = [
                f"# {ctx['purpose']} ({ctx['prompt_version']})\n",
                "## system\n",
                body["system"],
            ]
            for message in body["messages"]:
                parts += [f"\n## {message['role']}\n", message["content"]]
            parts += [
                "\n## answer format\nReply with ONLY a JSON object matching this schema, saved to",
                f"`{answer_path.name}`:\n```json",
                json.dumps(body["output_config"]["format"]["schema"], indent=1),
                "```",
            ]
            stem.with_suffix(".request.md").write_text("\n".join(parts), encoding="utf-8")
        if not await self._wait_for(answer_path):
            raise LLMResponsePendingError(
                f"Waiting for an answer: write {answer_path}",
                details={
                    "request": str(stem.with_suffix(".request.md")),
                    "answer": str(answer_path),
                    "purpose": ctx[
                        "purpose"
                    ],  # jd_parse | evaluate | repair: the UI names the step
                },
            )

        call_id = Ledger.new_id()
        request_key, response_key = f"llm/{call_id}/request.json", f"llm/{call_id}/response.json"
        raw_text = answer_path.read_text(encoding="utf-8")
        await self._storage.put(request_key, json.dumps(body, indent=1).encode())
        await self._storage.put(response_key, raw_text.encode())
        entry = LedgerEntry(
            **ctx,
            id=call_id,
            status="success",
            attempt=1,
            cost_usd=Decimal(0),
            latency_ms=0,
            request_key=request_key,
            response_key=response_key,
        )
        try:
            value = output_model.model_validate_json(_strip_code_fence(raw_text))
        except ValidationError as exc:
            entry.status, entry.error_code = "invalid_output", "LLM_INVALID_OUTPUT"
            entry.error_message = str(exc)[:2000]
            await self._ledger.record(entry)
            invalid = LLMInvalidOutputError(
                "LLM returned output that does not match the schema",
                details={"call_id": str(call_id), "errors": str(exc)[:2000]},
            )
            invalid.raw_text = raw_text
            raise invalid from exc
        await self._ledger.record(entry)
        self._log_attempt(entry)
        return LLMResult(
            value=value, call_id=call_id, cost_usd=Decimal(0), cache_hit=False, raw_text=raw_text
        )

    async def _wait_for(self, path: Path) -> bool:
        """Poll for a manual answer file for up to manual_llm_wait_seconds."""
        waited = 0.0
        while not await asyncio.to_thread(path.exists):
            if waited >= self._settings.manual_llm_wait_seconds:
                return False
            await self._sleep(0.5)
            waited += 0.5
        return True

    async def _try_cache[T: BaseModel](
        self, ctx: dict[str, Any], output_model: type[T]
    ) -> LLMResult[T] | None:
        source = await cache.find_cached(self._sessionmaker, ctx["request_hash"])
        if source is None or source.response_key is None:
            return None
        try:
            stored = json.loads(await self._storage.get(source.response_key))
            raw_text, _ = _content_of(stored)
            value = output_model.model_validate_json(_strip_code_fence(raw_text))
        except (OSError, ValueError, ValidationError) as error:
            log.warning(
                "llm_cache_unusable", source_call_id=str(source.id), error=type(error).__name__
            )
            return None

        usage = None
        if source.input_tokens is not None:
            usage = Usage(
                input_tokens=source.input_tokens,
                cached_input_tokens=source.cached_input_tokens or 0,
                output_tokens=source.output_tokens or 0,
                reasoning_tokens=source.reasoning_tokens or 0,
                cache_write_tokens=source.cache_write_tokens or 0,
            )
        call_id = await self._ledger.record(
            LedgerEntry(
                **ctx,
                status="success",
                attempt=1,
                usage=usage,
                cost_usd=Decimal(0),
                cache_hit=True,
                cache_source_call_id=source.id,
                latency_ms=0,
                request_key=source.request_key,
                response_key=source.response_key,
            )
        )
        log.info(
            "llm_call", purpose=ctx["purpose"], model=ctx["model"], cache_hit=True, cost_usd="0"
        )
        return LLMResult(
            value=value, call_id=call_id, cost_usd=Decimal(0), cache_hit=True, raw_text=raw_text
        )

    async def _price_or_raise(self, provider: str, provider_model: str) -> PriceSnapshot | None:
        async with self._sessionmaker() as session:
            price = await get_price(session, provider, provider_model, datetime.now(UTC))
        if price is not None:
            return price
        message = f"No model_prices row for {provider}/{provider_model}"
        if self._settings.is_prod:
            # PLAN.md §8: prod logs PRICE_MISSING and records cost as NULL.
            log.error(
                "price_missing", code="PRICE_MISSING", provider=provider, model=provider_model
            )
            return None
        raise PriceMissingError(
            f"{message}. Run `make seed-prices` (or add a price) before calling this model."
        )

    async def _send(self, body: dict[str, Any], api_key: str) -> _Attempt:
        started = time.perf_counter()

        def elapsed() -> int:
            return int((time.perf_counter() - started) * 1000)

        try:
            async with httpx.AsyncClient(
                base_url=self._settings.openrouter_base_url,
                timeout=self._settings.llm_timeout_seconds,
                transport=self._transport,
            ) as http:
                response = await http.post(
                    "/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.TimeoutException as exc:
            return _Attempt(
                None,
                None,
                LLMTimeoutError(f"LLM request timed out: {type(exc).__name__}"),
                elapsed(),
            )
        except httpx.TransportError as exc:
            return _Attempt(
                None,
                None,
                LLMProviderError(f"LLM connection failed: {type(exc).__name__}"),
                elapsed(),
            )

        try:
            data: dict[str, Any] | None = response.json()
        except ValueError:
            data = None
        status = response.status_code
        error: LLMError | None = None
        if status == 429:
            error = LLMRateLimitedError("LLM provider rate-limited the request")
            retry_after = response.headers.get("retry-after")
            if retry_after:
                error.details["retry_after"] = retry_after
        elif status >= 500:
            error = LLMProviderError(f"LLM provider error (HTTP {status})")
        elif status >= 400:
            detail = (data or {}).get("error", {}) if isinstance(data, dict) else {}
            message = detail.get("message") if isinstance(detail, dict) else None
            error = LLMRequestRejectedError(
                f"LLM request rejected (HTTP {status}): {message or 'no detail'}"
            )
        elif not isinstance(data, dict):
            error = LLMProviderError("LLM provider returned a non-JSON body")
        elif data.get("error"):
            # OpenRouter can report upstream failures inside a 200 body.
            detail = data["error"]
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            error = LLMProviderError(f"LLM provider error: {message}")
        return _Attempt(status, data if isinstance(data, dict) else None, error, elapsed())

    async def _backoff(self, attempt: int, error: LLMError) -> None:
        delay = self._settings.llm_retry_base_seconds * (2 ** (attempt - 1))
        delay += random.uniform(0, self._settings.llm_retry_base_seconds)  # noqa: S311 - jitter
        retry_after = error.details.get("retry_after")
        if retry_after is not None:
            with contextlib.suppress(ValueError):
                delay = max(delay, min(float(retry_after), _MAX_RETRY_AFTER_SECONDS))
        await self._sleep(delay)

    async def _call_with_retries[T: BaseModel](
        self,
        ctx: dict[str, Any],
        body: dict[str, Any],
        price: PriceSnapshot | None,
        provider: str,
        api_key: str,
        output_model: type[T],
    ) -> LLMResult[T]:
        max_attempts = self._settings.llm_max_retries + 1
        request_bytes = json.dumps(body, ensure_ascii=False, indent=1).encode()

        for attempt in range(1, max_attempts + 1):
            call_id = Ledger.new_id()
            request_key = f"llm/{call_id}/request.json"
            await self._storage.put(request_key, request_bytes)

            if provider == "anthropic":
                result = await self._send_anthropic(body, api_key)
            else:
                result = await self._send(body, api_key)
            response_key = None
            if result.body is not None:
                response_key = f"llm/{call_id}/response.json"
                await self._storage.put(
                    response_key, json.dumps(result.body, ensure_ascii=False, indent=1).encode()
                )

            usage = _usage_from(result.body) if result.body else None
            cost = compute_cost(usage, price) if (usage and price) else None
            if usage is None and price is not None:
                # Failed attempts without usage cost nothing we can see; a 200 without usage
                # is logged loudly because we refuse to estimate tokens.
                cost = Decimal(0)
                if result.error is None:
                    log.error("llm_usage_missing", call_id=str(call_id))
            provider_cost = _provider_cost(result.body) if result.body else None
            provider_request_id = result.body.get("id") if result.body else None

            entry = LedgerEntry(
                **ctx,
                id=call_id,
                status="success",
                attempt=attempt,
                usage=usage,
                price=price,
                cost_usd=cost,
                provider_reported_cost_usd=provider_cost,
                provider_request_id=str(provider_request_id) if provider_request_id else None,
                latency_ms=result.latency_ms,
                request_key=request_key,
                response_key=response_key,
            )

            if result.error is not None:
                entry.status = "error"
                entry.error_code = result.error.code
                entry.error_message = result.error.message[:2000]
                await self._ledger.record(entry)
                self._log_attempt(entry)
                if result.error.retryable and attempt < max_attempts:
                    await self._backoff(attempt, result.error)
                    continue
                raise result.error

            if result.body is None:  # pragma: no cover - _send sets an error without a body
                raise LLMProviderError("LLM provider returned no body")
            raw_text, finish_reason = _content_of(result.body)
            if finish_reason == "refusal":
                # Tokens were spent: record the cost, but don't retry or repair.
                refused = LLMRefusedError("The model declined to answer this request")
                entry.status, entry.error_code = "error", refused.code
                entry.error_message = json.dumps(result.body.get("stop_details"))[:2000]
                await self._ledger.record(entry)
                self._log_attempt(entry)
                raise refused
            try:
                if finish_reason == "length":
                    raise ValueError("response truncated (finish_reason=length)")
                value = output_model.model_validate_json(_strip_code_fence(raw_text))
            except (ValueError, ValidationError) as exc:
                entry.status = "invalid_output"
                entry.error_code = "LLM_INVALID_OUTPUT"
                entry.error_message = str(exc)[:2000]
                await self._ledger.record(entry)
                self._log_attempt(entry)
                invalid = LLMInvalidOutputError(
                    "LLM returned output that does not match the schema",
                    details={"call_id": str(call_id), "errors": str(exc)[:2000]},
                )
                invalid.raw_text = raw_text
                raise invalid from exc

            await self._ledger.record(entry)
            self._log_attempt(entry)
            return LLMResult(
                value=value, call_id=call_id, cost_usd=cost, cache_hit=False, raw_text=raw_text
            )

        raise AssertionError("unreachable: retry loop always returns or raises")  # pragma: no cover

    @staticmethod
    def _log_attempt(entry: LedgerEntry) -> None:
        log.info(
            "llm_call",
            call_id=str(entry.id),
            purpose=entry.purpose,
            model=entry.model,
            attempt=entry.attempt,
            status=entry.status,
            error_code=entry.error_code,
            latency_ms=entry.latency_ms,
            input_tokens=entry.usage.input_tokens if entry.usage else None,
            output_tokens=entry.usage.output_tokens if entry.usage else None,
            cost_usd=str(entry.cost_usd) if entry.cost_usd is not None else None,
            provider_cost_usd=(
                str(entry.provider_reported_cost_usd)
                if entry.provider_reported_cost_usd is not None
                else None
            ),
        )
