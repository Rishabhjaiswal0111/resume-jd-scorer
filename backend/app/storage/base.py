"""Storage interface. Business code depends on this, never on a concrete backend."""

from typing import Protocol


class Storage(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...

    async def healthcheck(self) -> None:
        """Raise if the storage backend is not usable."""
        ...
