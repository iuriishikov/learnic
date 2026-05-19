"""Physically remove a soft-deleted file's blob from object storage.

The companion to :meth:`File.mark_deleted` — without this step,
soft-deleting a file frees its quota footprint (the DB row stops
being summed) but the underlying S3 / MinIO object lingers and
continues to cost storage at the cloud provider.

Driven asynchronously by TaskIQ: producers flip ``deleted_at`` in
the same transaction as their domain mutation and enqueue this
command **before** the commit. If the producer's transaction
later rolls back, the task arrives in the worker and sees a still-
live file row — and aborts. This means "schedule then rollback"
is safe; we never lose a blob that a domain operation didn't
actually intend to lose.

The DB row stays in place (``deleted_at != NULL``) as an audit
record. Blocks pointing at it keep working — column FKs are
``ON DELETE SET NULL``, and the photo-collage JSONB only carries
the file id, not the blob.
"""

import logging
from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PurgeFileFromStorageCommand:
    file_id: FileID


@final
class PurgeFileFromStorageCommandHandler:
    def __init__(
        self,
        files_gateway: FilesGateway,
        file_storage: FileStorage,
    ) -> None:
        self._files_gateway: Final = files_gateway
        self._file_storage: Final = file_storage

    async def run(self, data: PurgeFileFromStorageCommand) -> None:
        """Delete the underlying S3 / MinIO object for one soft-deleted file.

        No-ops when the row is missing or still live — both states
        indicate the producer's transaction rolled back after
        enqueuing the task. Idempotent on the storage side too:
        :meth:`FileStorage.delete` succeeds whether or not the
        object exists.
        """
        file = await self._files_gateway.with_id(data.file_id)
        if file is None:
            _logger.info(
                "file_purge.row_missing",
                extra={"file_id": str(data.file_id)},
            )
            return
        if not file.is_deleted:
            _logger.info(
                "file_purge.row_still_live",
                extra={"file_id": str(data.file_id)},
            )
            return
        await self._file_storage.delete(
            bucket=file.bucket.value,
            name=file.storage_name.value,
        )
        _logger.info(
            "file_purge.done",
            extra={
                "file_id": str(data.file_id),
                "bucket": file.bucket.value,
                "name": file.storage_name.value,
            },
        )
