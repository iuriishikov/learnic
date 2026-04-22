from dataclasses import dataclass
from typing import Protocol

from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File


@dataclass(slots=True, frozen=True)
class FileView:
    """Read-side projection — enough to build a storage URL."""

    oid: FileID
    storage_name: str
    bucket: str
    content_type: str


class FilesGateway(Protocol):
    """Write-side lookups for :class:`File`."""

    async def with_id(self, oid: FileID) -> File | None: ...


class FilesReader(Protocol):
    """Read-side queries returning :class:`FileView` projections."""

    async def with_id(self, oid: FileID) -> FileView | None: ...
