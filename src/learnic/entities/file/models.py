import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.user.models import UserID


@dataclass
class File(BaseEntity[FileID]):
    storage_name: StorageName
    bucket: StorageBucket
    content_type: ContentType
    size_bytes: FileSize
    uploaded_by: UserID
    uploaded_at: datetime
    deleted_at: datetime | None = field(default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def mark_deleted(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)

    @classmethod
    def create_file(
        cls,
        bucket: StorageBucket,
        content_type: ContentType,
        size_bytes: FileSize,
        uploaded_by: UserID,
    ) -> Self:
        """Build a new :class:`File` with an oid-derived storage name.

        The storage name is ``str(oid)`` with no extension — MIME is
        kept in ``content_type`` and in the S3 object metadata, so
        browsers still get the right ``Content-Type`` on fetch.
        """
        oid = FileID(uuid.uuid4())
        return cls(
            oid=oid,
            storage_name=StorageName(str(oid)),
            bucket=bucket,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            deleted_at=None,
        )
