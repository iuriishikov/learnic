"""unify course_enrollments + webinar_enrollments into one ``enrollments`` table

Replaces the two parallel aggregates with a single ``enrollments``
table + two 1:1 side-detail tables (``enrollment_course_details``,
``enrollment_webinar_details``), mirroring the
``Product`` / ``product_webinar_details`` pattern. Drops the
historical webinar-only ``DROPPED`` status — those rows are
migrated to ``REFUNDED`` (webinar drop semantically goes through
the refund flow in the new world).

Revision ID: aa1b8cde7f01
Revises: z0a7bcd5e6f7
Create Date: 2026-05-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "aa1b8cde7f01"
down_revision: Union[str, Sequence[str], None] = "z0a7bcd5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ---- 1. New PG enums ------------------------------------------- #
    enrollment_type = sa.Enum(
        "course", "webinar", name="enrollment_type",
    )
    enrollment_status = sa.Enum(
        "active", "completed", "refunded", name="enrollment_status",
    )
    enrollment_type.create(op.get_bind(), checkfirst=False)
    enrollment_status.create(op.get_bind(), checkfirst=False)

    # ---- 2. Create new tables -------------------------------------- #
    op.create_table(
        "enrollments",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "course", "webinar",
                name="enrollment_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "completed", "refunded",
                name="enrollment_status", create_type=False,
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
        sa.PrimaryKeyConstraint("oid"),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_enrollments_student_id", "enrollments", ["student_id"],
    )
    op.create_index(
        "ix_enrollments_type_status", "enrollments", ["type", "status"],
    )

    op.create_table(
        "enrollment_course_details",
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.PrimaryKeyConstraint("enrollment_id"),
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["enrollments.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["course_releases.oid"],
            ondelete="RESTRICT",
            name="fk_enrollment_course_details_release_id",
        ),
        sa.UniqueConstraint(
            "product_id", "student_id",
            name="uq_enrollment_course_details_product_student",
        ),
    )
    op.create_index(
        "ix_enrollment_course_details_release_id",
        "enrollment_course_details", ["release_id"],
    )

    op.create_table(
        "enrollment_webinar_details",
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("enrollment_id"),
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["enrollments.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"], ["cohorts.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "cohort_id", "student_id",
            name="uq_enrollment_webinar_details_cohort_student",
        ),
    )

    # ---- 3. Copy course enrollments -------------------------------- #
    op.execute(
        """
        INSERT INTO enrollments (oid, type, student_id, status, enrolled_at)
        SELECT oid, 'course'::enrollment_type, student_id,
               status::text::enrollment_status, enrolled_at
        FROM course_enrollments
        """,
    )
    op.execute(
        """
        INSERT INTO enrollment_course_details (
            enrollment_id, product_id, student_id,
            release_id, progress_percent, completed_at
        )
        SELECT oid, product_id, student_id,
               release_id, progress_percent, completed_at
        FROM course_enrollments
        """,
    )

    # ---- 4. Copy webinar enrollments — map DROPPED → REFUNDED ----- #
    op.execute(
        """
        INSERT INTO enrollments (oid, type, student_id, status, enrolled_at)
        SELECT oid, 'webinar'::enrollment_type, student_id,
               CASE
                   WHEN status::text = 'dropped' THEN 'refunded'
                   ELSE status::text
               END::enrollment_status,
               enrolled_at
        FROM webinar_enrollments
        """,
    )
    op.execute(
        """
        INSERT INTO enrollment_webinar_details (
            enrollment_id, cohort_id, student_id
        )
        SELECT oid, cohort_id, student_id
        FROM webinar_enrollments
        """,
    )

    # ---- 5. Drop old tables + their PG enums ----------------------- #
    op.drop_index(
        "ix_course_enrollments_release_id",
        table_name="course_enrollments",
    )
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


def downgrade() -> None:
    """Downgrade schema.

    Restores the two old tables and re-fills them from the unified
    one. Webinar rows previously migrated from ``DROPPED`` to
    ``REFUNDED`` come back as ``REFUNDED`` — the original
    distinction is lost.
    """
    # ---- 1. Recreate old PG enums ---------------------------------- #
    course_status = sa.Enum(
        "active", "completed", "refunded",
        name="course_enrollment_status",
    )
    webinar_status = sa.Enum(
        "active", "dropped", "completed", "refunded",
        name="webinar_enrollment_status",
    )
    course_status.create(op.get_bind(), checkfirst=False)
    webinar_status.create(op.get_bind(), checkfirst=False)

    # ---- 2. Recreate old tables ------------------------------------ #
    op.create_table(
        "course_enrollments",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "completed", "refunded",
                name="course_enrollment_status", create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "progress_percent", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "enrolled_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("oid"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["course_releases.oid"],
            ondelete="RESTRICT",
            name="fk_course_enrollments_release_id",
        ),
        sa.UniqueConstraint(
            "product_id", "student_id",
            name="uq_course_enrollments_product_student",
        ),
    )
    op.create_index(
        "ix_course_enrollments_student_id",
        "course_enrollments", ["student_id"],
    )
    op.create_index(
        "ix_course_enrollments_release_id",
        "course_enrollments", ["release_id"],
    )

    op.create_table(
        "webinar_enrollments",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "dropped", "completed", "refunded",
                name="webinar_enrollment_status", create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "enrolled_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.ForeignKeyConstraint(
            ["cohort_id"], ["cohorts.oid"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "cohort_id", "student_id",
            name="uq_webinar_enrollments_cohort_student",
        ),
    )
    op.create_index(
        "ix_webinar_enrollments_student_id",
        "webinar_enrollments", ["student_id"],
    )

    # ---- 3. Copy back from unified --------------------------------- #
    op.execute(
        """
        INSERT INTO course_enrollments (
            oid, product_id, student_id, status,
            progress_percent, enrolled_at, completed_at, release_id
        )
        SELECT e.oid, ecd.product_id, ecd.student_id,
               e.status::text::course_enrollment_status,
               ecd.progress_percent, e.enrolled_at, ecd.completed_at,
               ecd.release_id
        FROM enrollments e
        JOIN enrollment_course_details ecd
          ON ecd.enrollment_id = e.oid
        WHERE e.type = 'course'
        """,
    )
    op.execute(
        """
        INSERT INTO webinar_enrollments (
            oid, cohort_id, student_id, status, enrolled_at
        )
        SELECT e.oid, ewd.cohort_id, ewd.student_id,
               e.status::text::webinar_enrollment_status,
               e.enrolled_at
        FROM enrollments e
        JOIN enrollment_webinar_details ewd
          ON ewd.enrollment_id = e.oid
        WHERE e.type = 'webinar'
        """,
    )

    # ---- 4. Drop unified + its enums ------------------------------- #
    op.drop_index(
        "ix_enrollment_course_details_release_id",
        table_name="enrollment_course_details",
    )
    op.drop_table("enrollment_course_details")
    op.drop_table("enrollment_webinar_details")
    op.drop_index(
        "ix_enrollments_type_status", table_name="enrollments",
    )
    op.drop_index(
        "ix_enrollments_student_id", table_name="enrollments",
    )
    op.drop_table("enrollments")
    op.execute("DROP TYPE enrollment_status")
    op.execute("DROP TYPE enrollment_type")
