from typing import Final, NewType, final

from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
)
from learnic.entities.user.models import UserID

DefaultStorageBucket = NewType("DefaultStorageBucket", str)
"""Bucket name newly-created files land in by default.

Wired in IoC from ``S3Config.bucket`` so application code stays free
of infrastructure imports. A ``NewType`` over ``str`` keeps the DI
graph statically distinguishable from arbitrary strings.
"""


@final
class FileUploadService:
    """Upload bytes to object storage and persist a matching ``File`` row.

    Encapsulates the five-line dance previously inlined in every
    avatar/cover/product-creation handler:

    1. wrap content-type, size and bucket into VOs;
    2. construct a ``File`` entity (oid-derived storage name);
    3. ``put`` bytes into object storage;
    4. enqueue the entity through ``EntitySaver``;
    5. ``flush`` so the row exists for FK-referencing inserts that
       follow in the same transaction.

    The companion :meth:`replace` collapses the second duplicated
    block — three cover/avatar handlers also share the "soft-delete
    the file we're replacing" tail.

    Returns the persisted ``File`` so callers can both link it
    (``parent.set_cover(file.oid)``) and inspect attributes for
    follow-up logic.

    The S3 ``put`` runs before the row is flushed; on a later
    rollback the blob is orphaned and swept by the file-lifecycle
    worker — same behaviour as the previous inlined code.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        file_storage: FileStorage,
        files_gateway: FilesGateway,
        default_bucket: DefaultStorageBucket,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._file_storage: Final = file_storage
        self._files_gateway: Final = files_gateway
        self._default_bucket: Final = default_bucket

    async def upload(
        self,
        data: bytes,
        content_type: str,
        uploaded_by: UserID,
    ) -> File:
        """Persist a new ``File`` and upload its bytes to storage.

        Args:
            data: Raw bytes of the uploaded file.
            content_type: MIME type as supplied by the client. Wrapped
                in :class:`ContentType` so VO-level validation applies.
            uploaded_by: Acting user; written to ``File.uploaded_by``.

        Returns:
            The persisted ``File`` entity (flushed, so ``oid`` is safe
            to reference from FK-bearing inserts in the same
            transaction).
        """
        bucket = StorageBucket(self._default_bucket)
        file = File.create_file(
            bucket=bucket,
            content_type=ContentType(content_type),
            size_bytes=FileSize(len(data)),
            uploaded_by=uploaded_by,
        )
        await self._file_storage.put(
            bucket=bucket.value,
            name=file.storage_name.value,
            data=data,
            content_type=content_type,
        )
        self._entity_saver.add_one(file)
        await self._transaction.flush()
        return file

    async def soft_delete_previous(
        self,
        previous_file_id: FileID | None,
    ) -> None:
        """Mark the file being replaced as deleted.

        Idempotent: no-ops when ``previous_file_id`` is ``None``, when
        the row is missing, or when it is already soft-deleted. The S3
        blob is left in place — the file-lifecycle worker reaps it
        asynchronously, same as before.
        """
        if previous_file_id is None:
            return
        previous_file = await self._files_gateway.with_id(previous_file_id)
        if previous_file is not None and not previous_file.is_deleted:
            previous_file.mark_deleted()
