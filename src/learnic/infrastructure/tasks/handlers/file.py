"""TaskIQ handlers for file-aggregate background work."""

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.file.purge_from_storage import (
    PurgeFileFromStorageCommand,
    PurgeFileFromStorageCommandHandler,
)
from learnic.entities.file.ids import FileID
from learnic.infrastructure.tasks.broker import broker


@broker.task
@inject
async def purge_file_from_storage_task(
    file_id: FileID,
    attempt: int,
    force_release_pinned: bool,
    handler: FromDishka[PurgeFileFromStorageCommandHandler],
) -> None:
    """Delete the S3 / MinIO blob for one soft-deleted file.

    Producer enqueues this right after :meth:`File.mark_deleted`; the
    handler verifies the row is actually soft-deleted before touching
    storage and re-enqueues itself (incrementing ``attempt``) while the
    row is still live, so neither "schedule then commit" nor "schedule
    then rollback" can orphan a blob or delete a live file.

    ``force_release_pinned`` is set only by the over-quota reconcile
    job; it tells the handler to skip its defensive release re-check
    and purge even a blob a published release still pins (the release
    degrades to a missing-media placeholder).
    """
    await handler.run(
        PurgeFileFromStorageCommand(
            file_id=file_id,
            attempt=attempt,
            force_release_pinned=force_release_pinned,
        ),
    )
