from app.core.logging import _redact_secrets


def test_redacts_secret_like_keys() -> None:
    event = {
        "event": "llm_call",
        "api_key": "sk-123",
        "Authorization": "Bearer x",
        "db_password": "pw",
        "model": "deepseek-flash",
    }
    out = _redact_secrets(None, "info", event)
    assert out["api_key"] == "***"
    assert out["Authorization"] == "***"
    assert out["db_password"] == "***"
    assert out["model"] == "deepseek-flash"


def test_token_counts_are_not_redacted_but_tokens_are() -> None:
    out = _redact_secrets(
        None,
        "info",
        {"input_tokens": 10, "output_tokens": 5, "access_token": "t", "refresh_token": "r"},
    )
    assert out == {
        "input_tokens": 10,
        "output_tokens": 5,
        "access_token": "***",
        "refresh_token": "***",
    }
