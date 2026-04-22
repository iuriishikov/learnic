from typing import Protocol


class FileStorage(Protocol):
    """S3-compatible object storage access.

    ``bucket`` is passed explicitly on every call so that callers can mix
    files from different buckets in one process — the adapter itself
    does not remember a single "default" bucket.
    """

    async def put(
        self,
        bucket: str,
        name: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None: ...

    async def get(self, bucket: str, name: str) -> bytes | None: ...

    async def delete(self, bucket: str, name: str) -> None: ...

    async def presigned_get_url(
        self,
        bucket: str,
        name: str,
        expires_in: int = 3600,
    ) -> str: ...
