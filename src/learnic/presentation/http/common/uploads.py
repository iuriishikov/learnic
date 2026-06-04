"""Upload helpers shared between routes that accept ``UploadFile`` bodies."""

import os
from collections.abc import AsyncIterator
from typing import Final, final

from fastapi import UploadFile

from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.file.errors import FileTooLargeError

_DEFAULT_CONTENT_TYPE: Final = "application/octet-stream"


@final
class _UploadFileSource:
    """Adapt a spooled ``UploadFile`` to the ``IncomingUpload`` Protocol.

    Yields the body in bounded chunks straight off the spooled temp
    file so the storage adapter can stream it to object storage
    without the whole payload ever entering memory.
    """

    def __init__(
        self,
        file: UploadFile,
        *,
        size: int,
        content_type: str,
    ) -> None:
        self._file: Final = file
        self._size: Final = size
        self._content_type: Final = content_type

    @property
    def size(self) -> int:
        return self._size

    @property
    def content_type(self) -> str:
        return self._content_type

    async def stream(self, chunk_size: int) -> AsyncIterator[bytes]:
        await self._file.seek(0)
        while True:
            chunk = await self._file.read(chunk_size)
            if not chunk:
                break
            yield chunk


async def open_upload(
    file: UploadFile,
    *,
    max_bytes: int,
) -> IncomingUpload:
    """Validate an upload's size and wrap it for streaming.

    The size is read from the already-spooled ``UploadFile`` — the
    ASGI layer receives the whole body and tracks its length before
    the handler runs — so the per-call-site cap is enforced up front
    without pulling the file into memory, and the true size is
    available for the storage-quota pre-check. The returned
    :class:`IncomingUpload` streams the body in chunks on demand; no
    byte is read into RAM until the storage adapter pulls it.

    The size cap is **mandatory** and keyword-only: routes must import
    the matching constant from
    :mod:`learnic.presentation.http.common.upload_limits` and pass it
    explicitly. There is no global default — omitting ``max_bytes`` is
    a ``TypeError`` at runtime and a mypy error at static-analysis
    time. This forces "how big can this particular upload be" to be
    visible at the call site.

    Args:
        file: Incoming ``multipart/form-data`` field.
        max_bytes: Per-call-site cap in bytes. See ``upload_limits.py``
            for the standard constants.

    Returns:
        An :class:`IncomingUpload` exposing the known ``size``, the
        declared ``content_type`` (falling back to
        ``application/octet-stream``) and a chunked byte ``stream``.

    Raises:
        FileTooLargeError: Declared size exceeds ``max_bytes``; the
            error carries ``max_bytes`` as ``limit`` so the SPA can
            render "limit was X MB" without guessing.
    """
    size = file.size
    if size is None:
        # Multipart parsing always sets ``.size``; fall back to
        # measuring the spooled file by seeking, without reading it in.
        underlying = file.file
        underlying.seek(0, os.SEEK_END)
        size = underlying.tell()
        underlying.seek(0)
    if size > max_bytes:
        raise FileTooLargeError(max_bytes)
    content_type = file.content_type or _DEFAULT_CONTENT_TYPE
    return _UploadFileSource(
        file,
        size=size,
        content_type=content_type,
    )
