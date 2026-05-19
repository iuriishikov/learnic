from dataclasses import dataclass
from typing import Protocol

from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class FileMeta:
    """Raw read-side projection of a ``files`` row.

    Carries everything needed to mint a presigned URL plus the
    metadata a UI needs to render a player or download tile
    (``content_type``, ``size_bytes``). Readers produce this shape;
    query handlers upgrade it into :class:`FileView` by signing a
    URL via :class:`FileStorage`.

    ``size_bytes`` is exposed so application-layer policies (storage
    quotas, eligibility checks, total-size displays) can run without
    a second round-trip to the write-side :class:`File` entity.
    """

    oid: FileID
    storage_name: str
    bucket: str
    content_type: str
    size_bytes: int


@dataclass(slots=True, frozen=True)
class FileView:
    """Wire-ready file projection — a :class:`FileMeta` plus a
    short-lived presigned-storage URL.

    Constructed exclusively via :meth:`of` / :meth:`of_optional` so
    you cannot forget to sign the URL. Query handlers build it once
    from a :class:`FileMeta` they receive from a reader; Pydantic
    schemas mirror its attributes through ``from_attributes=True``
    and auto-map without manual ``from_view`` boilerplate.

    ``storage_name`` and ``bucket`` are intentionally **absent** —
    the URL is the only thing the SPA cares about, and exposing the
    raw storage path would leak infrastructure detail (bucket name,
    key layout) into every response.
    """

    oid: FileID
    content_type: str
    size_bytes: int
    url: str

    @classmethod
    async def of(
        cls,
        meta: FileMeta,
        storage: FileStorage,
        *,
        ttl_seconds: int = 3600,
    ) -> "FileView":
        """Sign a presigned URL for ``meta`` and return a ready view.

        Args:
            meta: Raw projection from a reader.
            storage: File-storage adapter (already injected into the
                calling handler).
            ttl_seconds: Lifetime of the presigned URL, in seconds.
                Defaults to one hour, matching the underlying
                :meth:`FileStorage.presigned_get_url` default. Use a
                larger value for long-lived editor sessions (e.g.
                course-content drafts), a smaller value for one-shot
                redirects.

        Returns:
            A frozen :class:`FileView` whose ``url`` is the signed
            short-lived storage URL.
        """
        url = await storage.presigned_get_url(
            meta.bucket, meta.storage_name, expires_in=ttl_seconds,
        )
        return cls(
            oid=meta.oid,
            content_type=meta.content_type,
            size_bytes=meta.size_bytes,
            url=url,
        )

    @classmethod
    async def of_optional(
        cls,
        meta: FileMeta | None,
        storage: FileStorage,
        *,
        ttl_seconds: int = 3600,
    ) -> "FileView | None":
        """Same as :meth:`of`, but returns ``None`` for ``meta=None``.

        The common case at the boundary of optional file fields
        (``user.avatar``, ``product.cover``, ``lesson_block.file``):
        the reader may return ``None``, the handler shouldn't have
        to repeat the ``if meta is None`` guard.
        """
        if meta is None:
            return None
        return await cls.of(meta, storage, ttl_seconds=ttl_seconds)


class FilesGateway(Protocol):
    """Write-side lookups for :class:`File`."""

    async def with_id(self, oid: FileID) -> File | None: ...


class FilesReader(Protocol):
    """Read-side queries returning :class:`FileMeta` projections."""

    async def with_id(self, oid: FileID) -> FileMeta | None: ...

    async def with_ids(self, oids: list[FileID]) -> dict[FileID, FileMeta]:
        """Batch-fetch file metadata by id.

        Returns a dict keyed by the requested ids; ids that don't
        correspond to a live (non-soft-deleted) file are absent
        from the result. Empty ``oids`` returns an empty dict
        without touching the database.

        Used by query handlers that need to enrich a deep tree of
        domain objects (e.g. a course draft with many file-backed
        blocks) without an N+1 round-trip.
        """
        ...

    async def file_ids_for_product(
        self,
        product_id: ProductID,
    ) -> list[FileID]:
        """Return every live file referenced from one product.

        Walks the same three file-backed block paths as the quota
        aggregate (file / video-file / photo-collage) and adds the
        product's cover. Deduplicated, soft-deleted excluded.
        Used by ``DeleteProductCommandHandler`` to soft-delete +
        S3-purge the file rows that lose their last reference
        when the product is hard-deleted (FKs are
        ``ON DELETE SET NULL``, so without this sweep the rows
        would linger as orphans).
        """
        ...
