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
    handler: FromDishka[PurgeFileFromStorageCommandHandler],
) -> None:
    """Delete the S3 / MinIO blob for one soft-deleted file.

    Producer enqueues this right after :meth:`File.mark_deleted`;
    the handler verifies the row is actually soft-deleted before
    touching storage, so "schedule then rollback" is safe.
    """
    await handler.run(PurgeFileFromStorageCommand(file_id=file_id))
