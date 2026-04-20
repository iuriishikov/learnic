from typing import Protocol


class FileStorage(Protocol):
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...

    async def presigned_get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str: ...
