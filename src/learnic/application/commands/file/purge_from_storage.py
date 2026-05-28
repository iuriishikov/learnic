"""Physically remove a soft-deleted file's blob and its DB row.

The companion to :meth:`File.mark_deleted` — without this step,
soft-deleting a file frees its quota footprint (the DB row stops
being summed) but the underlying S3 / MinIO object lingers and
continues to cost storage at the cloud provider. After this task
runs, neither the blob nor the row remain.

Driven asynchronously by TaskIQ: producers flip ``deleted_at`` in
the same transaction as their domain mutation and enqueue this
command **before** the commit. If the producer's transaction
later rolls back, the task arrives in the worker and sees a still-
live file row — and aborts. "Schedule then rollback" therefore
loses nothing.

Three steps run in order (all inside the worker's own transaction):

1. Delete the S3 / MinIO blob.
2. Excise the file from every photo-collage block whose JSONB
   ``items`` array still references it. A collage is a *gallery*
   of independent items — losing one to quota enforcement does
   not invalidate the rest, so the surrounding block stays in
   place (even if it ends up empty). ``file_blocks`` and
   ``video_file_blocks`` get treated more bluntly in step 3:
   ``ON DELETE CASCADE`` on the FK drops the whole block, because
   a single-file/video block without its file is meaningless.
3. Hard-delete the ``files`` row.

Product rule (per the storage-quota grace flow): if a file goes
because the author exceeded their plan and missed the grace
period, single-file blocks that referenced it go with it; collage
blocks lose just the offending item. Replace paths (``update_file``
/ ``update_video_file`` / collage replace) update the block to
point at the new file BEFORE this task fires, so neither the
CASCADE nor the collage-excise touch the new state.
"""

import logging
from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import Transaction
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
        transaction: Transaction,
        files_gateway: FilesGateway,
        block_gateway: LessonBlockGateway,
        file_storage: FileStorage,
    ) -> None:
        self._transaction: Final = transaction
        self._files_gateway: Final = files_gateway
        self._block_gateway: Final = block_gateway
        self._file_storage: Final = file_storage

    async def run(self, data: PurgeFileFromStorageCommand) -> None:
        """Erase the S3 blob, the dependent collage blocks, and the row.

        No-ops when the row is missing or still live — either state
        indicates the producer's transaction rolled back after
        enqueuing the task. The S3 ``delete`` is idempotent on the
        storage side, so a retried task that already removed the
        blob is also safe.
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
        await self._block_gateway.remove_file_from_collages(data.file_id)
        await self._files_gateway.delete(data.file_id)
        await self._transaction.commit()
        _logger.info(
            "file_purge.done",
            extra={
                "file_id": str(data.file_id),
                "bucket": file.bucket.value,
                "name": file.storage_name.value,
            },
        )
