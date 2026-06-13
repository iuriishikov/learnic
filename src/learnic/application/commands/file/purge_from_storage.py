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

from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.file.ids import FileID

_logger = logging.getLogger(__name__)

MAX_PURGE_RETRY_ATTEMPTS: Final = 10
"""How many times the purge task re-enqueues itself while it still sees
a live (not-yet-soft-deleted) row.

The producer enqueues the purge *before* committing its soft-delete, so
a fast worker can observe the row still live. Rather than give up — which
would orphan the blob once the producer commits — the task re-enqueues a
bounded number of times until it sees ``deleted_at`` set. If the producer
instead rolled back, the row stays live forever and the retries exhaust
harmlessly (the blob is a legitimate live file that must NOT be deleted)."""


@dataclass(slots=True, frozen=True)
class PurgeFileFromStorageCommand:
    file_id: FileID
    attempt: int = 0


@final
class PurgeFileFromStorageCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        files_gateway: FilesGateway,
        block_gateway: LessonBlockGateway,
        file_storage: FileStorage,
        task_scheduler: TaskScheduler,
    ) -> None:
        self._transaction: Final = transaction
        self._files_gateway: Final = files_gateway
        self._block_gateway: Final = block_gateway
        self._file_storage: Final = file_storage
        self._task_scheduler: Final = task_scheduler

    async def run(self, data: PurgeFileFromStorageCommand) -> None:
        """Erase the S3 blob, the dependent collage blocks, and the row.

        No-ops when the row is missing. When the row is still live the
        producer's soft-delete has not committed yet (a fast worker beat
        the commit) **or** the producer rolled back — the two are
        indistinguishable here, so the task re-enqueues itself up to
        :data:`MAX_PURGE_RETRY_ATTEMPTS` times until it sees
        ``deleted_at`` set, then gives up (leaving a rolled-back file
        correctly intact). The S3 ``delete`` is idempotent on the
        storage side, so a retried task that already removed the blob is
        also safe.

        Final release guard: even when the row is soft-deleted, the
        worker re-checks :meth:`FilesGateway.is_referenced_by_release`
        and aborts if a published release still pins the file. That
        check covers all three mirror shapes — the single-file and
        video-file FK mirrors AND the photo-collage JSONB ``items``
        array — so a release published before this task runs is always
        seen. The producer
        (:meth:`FileUploadService.soft_delete_previous`) already gates
        on this, so a hit here means a producer skipped the check — the
        warning makes that observable while preventing the data-losing
        physical delete (a release shares the exact blob, it does not
        own a copy).

        Accepted residual race: a release that commits its snapshot in
        the narrow window *between* this guard's read and this task's
        own commit can still end up pointing at a just-deleted blob
        (READ COMMITTED). It is rare (publish + free-the-same-file must
        interleave to the millisecond) and degrades to a missing-media
        placeholder, never a crash. Closing it fully would require a
        per-file advisory lock shared by publish and purge; deferred.
        """
        file = await self._files_gateway.with_id(data.file_id)
        if file is None:
            _logger.info(
                "file_purge.row_missing",
                extra={"file_id": str(data.file_id)},
            )
            return
        if not file.is_deleted:
            # Producer hasn't committed the soft-delete yet (or rolled
            # back). Re-enqueue so we converge once the commit lands,
            # instead of silently dropping the purge and orphaning the
            # blob. Bounded so a genuine rollback eventually stops.
            if data.attempt < MAX_PURGE_RETRY_ATTEMPTS:
                await self._task_scheduler.schedule_purge_file_from_storage(
                    data.file_id,
                    attempt=data.attempt + 1,
                )
            else:
                _logger.info(
                    "file_purge.row_still_live_giving_up",
                    extra={
                        "file_id": str(data.file_id),
                        "attempts": data.attempt,
                    },
                )
            return
        if await self._files_gateway.is_referenced_by_release(data.file_id):
            _logger.warning(
                "file_purge.release_pinned",
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
                # NB: not "name" — that key is reserved by logging.LogRecord
                # (the logger name) and raises KeyError in makeRecord.
                "storage_name": file.storage_name.value,
            },
        )
