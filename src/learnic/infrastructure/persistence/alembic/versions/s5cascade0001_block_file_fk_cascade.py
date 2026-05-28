"""switch file/video-file block FK on files to CASCADE

Storage-quota enforcement (and any other hard-delete of a file row)
now drops dependent blocks too: product policy is that an author
who exceeded their plan and missed the 14-day grace loses both the
files AND the blocks that pointed at them. Replace flows still
update the block to a new ``file_id`` before the parent file gets
deleted, so the CASCADE does nothing in those paths.

Photo-collage blocks reference files through a JSONB array with no
FK, so they are handled separately inside
``PurgeFileFromStorageCommandHandler`` (find every collage whose
``items`` array still points at the file being purged, then delete
those collage rows).

Revision ID: s5cascade0001
Revises: s4breach0003
Create Date: 2026-05-20 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "s5cascade0001"
down_revision: Union[str, Sequence[str], None] = "s4breach0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace SET NULL → CASCADE on file_blocks/video_file_blocks."""
    op.drop_constraint(
        "file_blocks_file_id_fkey",
        "file_blocks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_blocks_file_id_fkey",
        "file_blocks",
        "files",
        ["file_id"],
        ["oid"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "video_file_blocks_file_id_fkey",
        "video_file_blocks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "video_file_blocks_file_id_fkey",
        "video_file_blocks",
        "files",
        ["file_id"],
        ["oid"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Revert to SET NULL."""
    op.drop_constraint(
        "file_blocks_file_id_fkey",
        "file_blocks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_blocks_file_id_fkey",
        "file_blocks",
        "files",
        ["file_id"],
        ["oid"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "video_file_blocks_file_id_fkey",
        "video_file_blocks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "video_file_blocks_file_id_fkey",
        "video_file_blocks",
        "files",
        ["file_id"],
        ["oid"],
        ondelete="SET NULL",
    )
