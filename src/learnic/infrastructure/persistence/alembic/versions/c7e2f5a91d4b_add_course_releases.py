"""add course releases (entity + 6 snapshot tables) and enrollment.release_id

Revision ID: c7e2f5a91d4b
Revises: f1d8b62a4e07
Create Date: 2026-05-01 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c7e2f5a91d4b"
down_revision: Union[str, Sequence[str], None] = "f1d8b62a4e07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "course_releases",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("major", sa.Integer(), nullable=False),
        sa.Column("minor", sa.Integer(), nullable=False),
        sa.Column("patch", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "major",
                "minor",
                "patch",
                name="course_release_kind",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=5000), nullable=True),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("released_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["released_by"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "product_id",
            "ordinal",
            name="uq_course_releases_product_ordinal",
        ),
        sa.UniqueConstraint(
            "product_id",
            "major",
            "minor",
            "patch",
            name="uq_course_releases_product_version",
        ),
    )
    op.execute(
        "CREATE INDEX ix_course_releases_product_ordinal_desc "
        "ON course_releases (product_id, ordinal DESC)",
    )

    op.create_table(
        "course_release_modules",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("source_module_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["course_releases.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_course_release_modules_release_position",
        "course_release_modules",
        ["release_id", "position"],
    )

    op.create_table(
        "course_release_lessons",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("release_module_id", sa.Uuid(), nullable=False),
        sa.Column("source_lesson_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["course_releases.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["release_module_id"],
            ["course_release_modules.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_course_release_lessons_module_position",
        "course_release_lessons",
        ["release_module_id", "position"],
    )
    op.create_index(
        "ix_course_release_lessons_release_id",
        "course_release_lessons",
        ["release_id"],
    )

    op.create_table(
        "course_release_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("release_lesson_id", sa.Uuid(), nullable=False),
        sa.Column("source_block_id", sa.Uuid(), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "html",
                "latex",
                "rutube_video",
                name="lesson_block_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["course_releases.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["release_lesson_id"],
            ["course_release_lessons.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_course_release_blocks_lesson_position",
        "course_release_blocks",
        ["release_lesson_id", "position"],
    )
    op.create_index(
        "ix_course_release_blocks_release_id",
        "course_release_blocks",
        ["release_id"],
    )

    op.create_table(
        "course_release_html_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("html", sa.String(length=50000), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_table(
        "course_release_latex_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=50000), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_table(
        "course_release_rutube_video_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    # Pin every CourseEnrollment to the release that was current at
    # signup. Nullable in DB so this migration is safe to run on a
    # dev DB with stray enrollments; the entity / handler enforce
    # the value as required from now on.
    op.add_column(
        "course_enrollments",
        sa.Column("release_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_course_enrollments_release_id",
        "course_enrollments",
        "course_releases",
        ["release_id"],
        ["oid"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_course_enrollments_release_id",
        "course_enrollments",
        ["release_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_course_enrollments_release_id",
        table_name="course_enrollments",
    )
    op.drop_constraint(
        "fk_course_enrollments_release_id",
        "course_enrollments",
        type_="foreignkey",
    )
    op.drop_column("course_enrollments", "release_id")

    op.drop_table("course_release_rutube_video_blocks")
    op.drop_table("course_release_latex_blocks")
    op.drop_table("course_release_html_blocks")
    op.drop_index(
        "ix_course_release_blocks_release_id",
        table_name="course_release_blocks",
    )
    op.drop_index(
        "ix_course_release_blocks_lesson_position",
        table_name="course_release_blocks",
    )
    op.drop_table("course_release_blocks")
    op.drop_index(
        "ix_course_release_lessons_release_id",
        table_name="course_release_lessons",
    )
    op.drop_index(
        "ix_course_release_lessons_module_position",
        table_name="course_release_lessons",
    )
    op.drop_table("course_release_lessons")
    op.drop_index(
        "ix_course_release_modules_release_position",
        table_name="course_release_modules",
    )
    op.drop_table("course_release_modules")
    op.drop_index(
        "ix_course_releases_product_ordinal_desc",
        table_name="course_releases",
    )
    op.drop_table("course_releases")

    op.execute("DROP TYPE course_release_kind")
