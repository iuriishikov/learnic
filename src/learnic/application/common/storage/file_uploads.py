from typing import Final, NewType, final

from learnic.application.common.errors import WrongFileContentTypeError
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.storage.upload import IncomingUpload
from learnic.application.common.tasks.scheduler import TaskScheduler
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

IMAGE_CONTENT_TYPE_PREFIX: Final = "image/"
"""Single source of truth for the "this upload must be an image" rule
shared by the avatar / cover / experience-icon / product-cover flows."""


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

    The S3 ``put`` runs before the row is flushed: this ordering keeps
    a committed ``files`` row from ever pointing at a missing blob (the
    inverse — row first, then put — would leave the quota aggregate
    counting a file that storage never received on a put failure). The
    cost is that a rollback *after* a successful put orphans the blob,
    since there is no bucket-scanning reaper. Callers must therefore do
    every cheap precondition (auth, block-count limit, content-type)
    BEFORE calling this — see the file-block handlers — so the only
    residual orphan window is an unexpected post-put failure, which is
    rare. The deliberate-deletion path (``soft_delete_previous`` →
    ``purge_file_from_storage_task``) is self-healing and never leaks.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        file_storage: FileStorage,
        files_gateway: FilesGateway,
        task_scheduler: TaskScheduler,
        default_bucket: DefaultStorageBucket,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._file_storage: Final = file_storage
        self._files_gateway: Final = files_gateway
        self._task_scheduler: Final = task_scheduler
        self._default_bucket: Final = default_bucket

    async def upload_stream(
        self,
        upload: IncomingUpload,
        uploaded_by: UserID,
    ) -> File:
        """Stream an upload into storage and persist its ``File`` row.

        The byte count comes from ``upload.size`` — known up front
        because the ASGI layer fully receives and spools the body
        before the handler runs — so the ``File`` is built with its
        true size while the bytes are forwarded to object storage one
        chunk at a time, never materialising the whole file in memory.

        Args:
            upload: The incoming file: its known ``size``, declared
                ``content_type`` and a chunked byte ``stream``.
            uploaded_by: Acting user; written to ``File.uploaded_by``.

        Returns:
            The persisted ``File`` entity (flushed, so ``oid`` is safe
            to reference from FK-bearing inserts in the same
            transaction).
        """
        bucket = StorageBucket(self._default_bucket)
        file = File.create_file(
            bucket=bucket,
            content_type=ContentType(upload.content_type),
            size_bytes=FileSize(upload.size),
            uploaded_by=uploaded_by,
        )
        await self._file_storage.put_stream(
            bucket=bucket.value,
            name=file.storage_name.value,
            source=upload,
            size=upload.size,
            content_type=upload.content_type,
        )
        self._entity_saver.add_one(file)
        await self._transaction.flush()
        return file

    async def upload_image_stream(
        self,
        upload: IncomingUpload,
        uploaded_by: UserID,
    ) -> File:
        """Like :meth:`upload_stream` but rejects non-image uploads.

        Used by the avatar / cover / experience-icon / product-cover
        handlers, which are all documented image-only. Enforces the
        ``image/*`` content-type BEFORE any bytes reach storage, so a
        ``text/html`` or ``image/svg+xml`` payload cannot be stored and
        later served inline as a "photo" (content-type confusion). This
        mirrors the explicit prefix guard the note/blog image blocks
        already apply.

        Raises:
            WrongFileContentTypeError: ``upload.content_type`` is not an
                ``image/*`` type; HTTP 415.
        """
        if not upload.content_type.startswith(IMAGE_CONTENT_TYPE_PREFIX):
            raise WrongFileContentTypeError(
                file_id="<upload>",
                expected_prefix=IMAGE_CONTENT_TYPE_PREFIX,
                actual=upload.content_type,
            )
        return await self.upload_stream(upload, uploaded_by)

    async def previous_file_size(
        self,
        previous_file_id: FileID | None,
    ) -> int:
        """Return the live size in bytes of the file being replaced.

        Replace-semantic block handlers call this to credit
        ``freed_bytes`` in the quota pre-check
        (:meth:`EntitlementService.ensure_can_replace_upload`) so a
        same-size or smaller swap is not double-counted against the
        owner's cap.

        Mirrors :meth:`soft_delete_previous`'s liveness guard: a
        ``None`` id, a missing row, or an already-soft-deleted file
        frees nothing — none of those are counted in current usage —
        so each reports ``0``.
        """
        if previous_file_id is None:
            return 0
        previous_file = await self._files_gateway.with_id(previous_file_id)
        if previous_file is None or previous_file.is_deleted:
            return 0
        return previous_file.size_bytes.value

    async def soft_delete_previous(
        self,
        previous_file_id: FileID | None,
        *,
        evict_release_pinned: bool = False,
    ) -> bool:
        """Mark the file being freed as deleted and queue S3 purge.

        Idempotent: no-ops when ``previous_file_id`` is ``None``,
        when the row is missing, or when it is already soft-deleted.

        **Release guard.** A published release shares the exact
        ``files`` row of the draft it was snapshotted from — the
        snapshot copies ``file_id`` verbatim, it does not duplicate
        the blob. So a file the caller is freeing (a removed/replaced
        draft block, or a quota-eviction candidate) may still be the
        only copy a live release serves. By default
        (``evict_release_pinned=False``) such a file is left fully
        intact — not even soft-deleted — so a normal draft edit never
        strips media out of already-published content. This is the
        invariant every interactive editing path relies on.

        **Quota enforcement override.** ``evict_release_pinned=True``
        (passed only by the over-quota reconcile job, after the grace
        period) drops that protection: a release-pinned file IS
        soft-deleted and purged. The published release degrades to a
        missing-media placeholder (its mirror FK is ``ON DELETE SET
        NULL``). This is the deliberate "quota wins over release
        immutability" policy — the author was warned for the whole
        grace window. ``force_release_pinned`` is propagated to the
        purge task so its own release re-check does not veto the
        physical delete.

        Side effect: when the file is freed, enqueues
        :func:`purge_file_from_storage_task` so the worker physically
        removes the S3 blob shortly after the caller's transaction
        commits — that's how the user's plan quota actually frees up
        space on the cloud provider, not just inside the DB
        aggregate. The task re-checks ``deleted_at`` before touching
        storage, so a producer that rolls back after this call does
        not leak a deletion to S3.

        Args:
            previous_file_id: File to free, or ``None`` for a no-op.
            evict_release_pinned: When ``True``, evict the file even
                if a published release still pins it. Default ``False``
                spares release-pinned files (interactive edits).

        Returns:
            ``True`` if the file was soft-deleted and queued for
            purge; ``False`` when it was spared — a no-op id /
            missing / already-deleted row, or a release pins it and
            ``evict_release_pinned`` is ``False``. The reconcile job
            uses this to credit ``freed_bytes`` only for files it
            genuinely evicted.
        """
        if previous_file_id is None:
            return False
        previous_file = await self._files_gateway.with_id(previous_file_id)
        if previous_file is None or previous_file.is_deleted:
            return False
        pinned_by_release = await self._files_gateway.is_referenced_by_release(
            previous_file_id,
        )
        if pinned_by_release and not evict_release_pinned:
            # A published release still serves this exact blob and the
            # caller is an interactive edit, not quota enforcement.
            # Freeing it would strip media out of immutable,
            # already-published content, so leave it untouched.
            return False
        previous_file.mark_deleted()
        await self._task_scheduler.schedule_purge_file_from_storage(
            previous_file_id,
            force_release_pinned=pinned_by_release,
        )
        return True
