"""add cohort tables

Revision ID: e5b71d92f048
Revises: d2f8a91c4e6b
Create Date: 2026-04-28 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b71d92f048"
down_revision: Union[str, Sequence[str], None] = "d2f8a91c4e6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cohorts",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("webinar_id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("max_participants", sa.Integer(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column(
            "enrollment_status",
            sa.Enum(
                "open",
                "closed",
                "full",
                name="cohort_enrollment_status",
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "lifecycle_status",
            sa.Enum(
                "upcoming",
                "active",
                "completed",
                "cancelled",
                name="cohort_lifecycle_status",
            ),
            nullable=False,
            server_default="upcoming",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["webinar_id"],
            ["product_webinar_details.product_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["host_id"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_cohorts_webinar_id",
        "cohorts",
        ["webinar_id"],
    )
    op.create_index(
        "ix_cohorts_host_id",
        "cohorts",
        ["host_id"],
    )

    op.create_table(
        "webinar_schedules",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("rrule", sa.String(length=1024), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["cohorts.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_webinar_schedules_cohort_id",
        "webinar_schedules",
        ["cohort_id"],
    )

    op.create_table(
        "webinar_sessions",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column(
            "original_starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "rescheduled",
                "cancelled",
                "completed",
                name="webinar_session_status",
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column(
            "cancellation_reason",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "stream_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "recording_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
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
            ["schedule_id"],
            ["webinar_schedules.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "schedule_id",
            "original_starts_at",
            name="uq_webinar_sessions_schedule_original_starts",
        ),
    )
    op.create_index(
        "ix_webinar_sessions_cohort_id_starts_at",
        "webinar_sessions",
        ["cohort_id", "starts_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_webinar_sessions_cohort_id_starts_at",
        table_name="webinar_sessions",
    )
    op.drop_table("webinar_sessions")

    op.drop_index(
        "ix_webinar_schedules_cohort_id",
        table_name="webinar_schedules",
    )
    op.drop_table("webinar_schedules")

    op.drop_index("ix_cohorts_host_id", table_name="cohorts")
    op.drop_index("ix_cohorts_webinar_id", table_name="cohorts")
    op.drop_table("cohorts")

    op.execute("DROP TYPE webinar_session_status")
    op.execute("DROP TYPE cohort_lifecycle_status")
    op.execute("DROP TYPE cohort_enrollment_status")
