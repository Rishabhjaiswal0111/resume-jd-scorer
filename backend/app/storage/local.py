"""Local-disk storage for development."""

import asyncio
import uuid
from pathlib import Path


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Storage key escapes root: {key!r}")
        return path

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Unique temp name: two concurrent writers of the same key (the same file uploaded
            # twice at once) must not share, and then lose, one temp file.
            tmp = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # atomic on the same filesystem

        await asyncio.to_thread(_write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).exists)

    async def healthcheck(self) -> None:
        def _check() -> None:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".healthcheck"
            probe.write_bytes(b"ok")

        await asyncio.to_thread(_check)
