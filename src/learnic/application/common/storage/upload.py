"""Application-layer view of an upload whose bytes are streamed.

The ASGI layer (Starlette's multipart parser) fully receives the
request body and spools each file part to a temporary file on disk
**before** the route handler runs, tracking the exact byte count as it
does so. By the time a command handler sees an upload its ``size`` is
therefore already known without reading a single byte into memory —
which is what lets the storage-quota pre-check run on the true size
*before* anything is written to object storage, exactly as it did when
the whole file was buffered in RAM.

:class:`IncomingUpload` is that spooled upload as the application sees
it: the known ``size`` and declared ``content_type`` plus a ``stream``
that yields the bytes in bounded chunks so the storage adapter can
forward them to object storage without ever holding the whole file.
The HTTP layer adapts FastAPI's ``UploadFile`` to this Protocol; the
application and entities never import Starlette.
"""

from collections.abc import AsyncIterator
from typing import Protocol


class IncomingUpload(Protocol):
    """A file being uploaded, streamed rather than materialised.

    Command DTOs carry one of these in place of raw ``bytes`` so an
    arbitrarily large upload never lands fully in memory. ``size`` is
    the true byte count (known up front, see module docstring),
    ``content_type`` is the client-declared MIME, and ``stream``
    yields the body in chunks of at most ``chunk_size`` bytes.
    """

    @property
    def size(self) -> int: ...

    @property
    def content_type(self) -> str: ...

    def stream(self, chunk_size: int) -> AsyncIterator[bytes]: ...
