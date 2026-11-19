"""Typed application settings.

All configuration comes from environment variables (or the repo-root `.env`).
The app fails fast at startup if a required value is missing or invalid.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["dev", "test", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Works whether the process starts in backend/ or the repo root.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_env: AppEnv = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False
    # NoDecode: read the raw string so the validator below can split CSV.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- database ---
    database_url: str = (
        "postgresql+asyncpg://jdscorer:jdscorer_dev_password@localhost:5432/jdscorer"
    )
    db_pool_size: int = 5
    db_connect_timeout_seconds: float = 5.0

    # --- storage ---
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: Path = Path("./var/storage")

    # --- uploads (PLAN.md §11.8) ---
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20

    # --- LLM ---
    # "<provider>/<model as the provider names it>": anthropic/claude-haiku-5-5 or
    # openrouter/deepseek/deepseek-v4.1-flash
    llm_default_model: str = "anthropic/claude-haiku-5-5"
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 3  # retries for timeouts / 429 / 5xx (attempts = retries + 1)
    llm_retry_base_seconds: float = 1.0
    llm_temperature: float = 0.0  # OpenRouter only; Claude models reject sampling params
    llm_seed: int = 7  # OpenRouter only
    llm_max_output_tokens: int = 16000  # Claude: includes thinking tokens
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"  # Claude only
    llm_cache_enabled: bool = True
    # OpenRouter provider routing: never send resumes to providers that keep prompts.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_data_collection: Literal["allow", "deny"] = "deny"
    # manual/<name>: prompts are written here and answers are read back (no API, $0).
    manual_llm_dir: Path = Path("./var/manual_llm")
    # How long one request waits for the answer file before returning LLM_RESPONSE_PENDING.
    # The UI retries pending requests itself, so a short wait just avoids a failed run row
    # every few seconds while the answer is being written.
    manual_llm_wait_seconds: float = 20.0

    # --- scoring (PLAN.md §7) ---
    # Engine 1.1.0: off by default; knock-out criteria replace the flat -30 penalty.
    scoring_hard_fail_penalty: bool = False
    anthropic_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept `CORS_ORIGINS` as CSV (`http://a,http://b`) or a JSON list.

        NoDecode disables pydantic-settings' JSON decoding, so both forms
        arrive here as raw strings.
        """
        if not isinstance(value, str):
            return value
        if value.lstrip().startswith("["):
            return json.loads(value)
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
