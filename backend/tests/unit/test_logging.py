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
