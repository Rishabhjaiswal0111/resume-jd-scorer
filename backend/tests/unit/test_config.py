import pytest

from app.core.config import Settings


def test_cors_origins_accepts_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings().cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_accepts_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.test"]')
    assert Settings().cors_origins == ["http://a.test"]


def test_invalid_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production-ish")
    with pytest.raises(ValueError, match="app_env"):
        Settings()


def test_secrets_are_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-very-secret")
    settings = Settings()
    assert settings.openrouter_api_key is not None
    assert "very-secret" not in repr(settings)
    assert settings.openrouter_api_key.get_secret_value() == "sk-or-very-secret"
