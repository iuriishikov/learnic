from collections.abc import AsyncIterator
from typing import Protocol


class ByteStreamSource(Protocol):
    """Yields a payload's bytes in bounded chunks for a streaming write.

    Implemented at the HTTP boundary over a spooled ``UploadFile`` so
    the storage adapter can forward an upload to object storage one
    chunk at a time instead of buffering the whole body in memory.
    """

    def stream(self, chunk_size: int) -> AsyncIterator[bytes]: ...


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

    async def put_stream(
        self,
        bucket: str,
        name: str,
        source: ByteStreamSource,
        *,
        size: int,
        content_type: str | None = None,
    ) -> None:
        """Stream ``source`` into object storage without buffering it.

        ``size`` is the total byte count, known before the first byte
        is read (the ASGI layer spools the upload and tracks its
        length), so the adapter can pick a single PUT vs. a multipart
        upload. Implementations MUST forward the bytes chunk-by-chunk
        so an arbitrarily large file never lands fully in memory.
        """

    async def get(self, bucket: str, name: str) -> bytes | None: ...

    async def delete(self, bucket: str, name: str) -> None: ...

    async def presigned_get_url(
        self,
        bucket: str,
        name: str,
        expires_in: int = 3600,
    ) -> str: ...
