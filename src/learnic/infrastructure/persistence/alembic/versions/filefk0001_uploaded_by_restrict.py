"""files.uploaded_by FK CASCADE -> RESTRICT

A future hard-delete of a user must NOT silently cascade-drop their
``files`` rows — that would, via the ``file_blocks`` /
``video_file_blocks`` ON DELETE CASCADE FKs, also drop the blocks and
bypass the whole application file-lifecycle pipeline
(``soft_delete_previous``, the release-pin guard, the S3 purge),
orphaning blobs and potentially stripping media from OTHER authors'
notes the user only collaborated on. Switching this FK to RESTRICT
makes Postgres refuse such a delete; any future user-deletion saga must
route file removal through ``soft_delete_previous`` first.

Revision ID: filefk0001
Revises: revemail0001
Create Date: 2026-06-13 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "filefk0001"
down_revision: Union[str, Sequence[str], None] = "revemail0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "files_uploaded_by_fkey"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "files", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "files",
        "users",
        ["uploaded_by"],
        ["oid"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "files", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT,
        "files",
        "users",
        ["uploaded_by"],
        ["oid"],
        ondelete="CASCADE",
    )
