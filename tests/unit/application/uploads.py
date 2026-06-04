"""Test stand-in for the ``IncomingUpload`` streaming abstraction.

Unit tests mock :class:`FileUploadService`, so the actual bytes never
flow anywhere — handlers only read ``.size`` (quota pre-check) and
``.content_type`` (mime gates). :class:`FakeUpload` therefore carries
just those two, plus a trivial ``stream`` so it structurally satisfies
``learnic.application.common.storage.upload.IncomingUpload``.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FakeUpload:
    """Minimal ``IncomingUpload`` for command-handler unit tests.

    ``size`` defaults to 6 (the length of the ``b"binary"`` payload the
    pre-streaming tests used) so size-agnostic assertions keep working;
    quota tests pass an explicit ``size``.
    """

    content_type: str = "application/octet-stream"
    size: int = 6

    async def stream(self, chunk_size: int) -> AsyncIterator[bytes]:
        yield b""
