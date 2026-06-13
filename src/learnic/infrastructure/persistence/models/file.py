import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.file.constants import (
    CONTENT_TYPE_MAX_LEN,
    STORAGE_BUCKET_MAX_LEN,
    STORAGE_NAME_MAX_LEN,
)
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry

files_table = sa.Table(
    "files",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "storage_name",
        sa.String(STORAGE_NAME_MAX_LEN),
        nullable=False,
        unique=True,
    ),
    sa.Column(
        "bucket",
        sa.String(STORAGE_BUCKET_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "content_type",
        sa.String(CONTENT_TYPE_MAX_LEN),
        nullable=False,
    ),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column(
        "uploaded_by",
        sa.Uuid,
        # RESTRICT (not CASCADE): a future hard-delete of a user must NOT
        # silently drop their ``files`` rows (and, via file_blocks /
        # video_file_blocks CASCADE, the blocks) — that would bypass
        # soft_delete_previous, the release-pin guard, and the S3 purge,
        # orphaning blobs and stripping media from other authors' notes
        # the user only collaborated on. Any future user-deletion saga
        # must route file removal through soft_delete_previous first.
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "uploaded_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index(
        "ix_files_uploaded_by_active",
        "uploaded_by",
        postgresql_where=sa.text("deleted_at IS NULL"),
    ),
    sa.Index(
        "ix_files_deleted_at",
        "deleted_at",
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    ),
)


_mapped = False


def map_file_table() -> None:
    """Apply imperative mapping from :class:`File` to ``files_table``."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        File,
        files_table,
        properties={
            "oid": files_table.c.oid,
            "storage_name": composite(StorageName, files_table.c.storage_name),
            "bucket": composite(StorageBucket, files_table.c.bucket),
            "content_type": composite(ContentType, files_table.c.content_type),
            "size_bytes": composite(FileSize, files_table.c.size_bytes),
            "uploaded_by": files_table.c.uploaded_by,
            "uploaded_at": files_table.c.uploaded_at,
            "deleted_at": files_table.c.deleted_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
