"""add enrollment tables

Revision ID: f7a3c042e8d9
Revises: e5b71d92f048
Create Date: 2026-04-28 02:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a3c042e8d9"
down_revision: Union[str, Sequence[str], None] = "e5b71d92f048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "webinar_enrollments",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "dropped",
                "completed",
                "refunded",
                name="webinar_enrollment_status",
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["cohorts.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "cohort_id",
            "student_id",
            name="uq_webinar_enrollments_cohort_student",
        ),
    )
    op.create_index(
        "ix_webinar_enrollments_student_id",
        "webinar_enrollments",
        ["student_id"],
    )

    op.create_table(
        "course_enrollments",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "completed",
                "refunded",
                name="course_enrollment_status",
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "product_id",
            "student_id",
            name="uq_course_enrollments_product_student",
        ),
    )
    op.create_index(
        "ix_course_enrollments_student_id",
        "course_enrollments",
        ["student_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_course_enrollments_student_id",
        table_name="course_enrollments",
    )
    op.drop_table("course_enrollments")

    op.drop_index(
        "ix_webinar_enrollments_student_id",
        table_name="webinar_enrollments",
    )
    op.drop_table("webinar_enrollments")

    op.execute("DROP TYPE course_enrollment_status")
    op.execute("DROP TYPE webinar_enrollment_status")
