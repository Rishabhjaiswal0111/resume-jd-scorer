"""manual/ provider: prompt is written to disk, an answer file completes the call at $0."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from app.core.errors import LLMResponsePendingError
from app.llm.client import LLMClient
from tests.conftest import DbContext

pytestmark = pytest.mark.integration


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str


async def test_pending_then_answered(
    db: DbContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db.settings, "manual_llm_dir", tmp_path / "manual")
    client = LLMClient(db.settings, db.sessionmaker, db.storage)

    async def ask() -> object:
        return await client.complete_json(
            purpose="eval",
            prompt_version="test.v1",
            messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "q?"}],
            output_model=Answer,
            schema_name="answer",
            model="manual/claude-session",
        )

    with pytest.raises(LLMResponsePendingError) as pending:
        await ask()
    request = Path(pending.value.details["request"])
    assert "## user\n\nq?" in request.read_text()

    Path(pending.value.details["answer"]).write_text(json.dumps({"title": "ok"}))
    result = await ask()
    assert result.value == Answer(title="ok")  # type: ignore[attr-defined]
    assert result.cost_usd == Decimal(0)  # type: ignore[attr-defined]
