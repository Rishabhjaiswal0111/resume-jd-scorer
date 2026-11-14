from pathlib import Path

import pytest

from app.storage.local import LocalStorage


async def test_put_get_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    await storage.put("documents/abc/original.pdf", b"%PDF-1.7 data")

    assert await storage.exists("documents/abc/original.pdf")
    assert await storage.get("documents/abc/original.pdf") == b"%PDF-1.7 data"


async def test_missing_key_does_not_exist(tmp_path: Path) -> None:
    assert not await LocalStorage(tmp_path).exists("nope.txt")


async def test_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "root")
    with pytest.raises(ValueError, match="escapes root"):
        await storage.put("../outside.txt", b"x")


async def test_healthcheck_creates_root(tmp_path: Path) -> None:
    root = tmp_path / "new-root"
    await LocalStorage(root).healthcheck()
    assert root.is_dir()
