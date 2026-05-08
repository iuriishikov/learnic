from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.cohort.constants import (
    CANCELLATION_REASON_MAX_LEN,
    COHORT_NAME_MAX_LEN,
    IANA_TIMEZONE_MAX_LEN,
    RECORDING_URL_MAX_LEN,
    RRULE_MAX_LEN,
    SESSION_STREAM_URL_MAX_LEN,
)
from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
    WebinarSessionStatus,
)
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.cohort.value_objects import (
    CancellationReason,
    CohortName,
    IanaTimezone,
    RecordingUrl,
    RecurrenceRule,
)
from learnic.entities.product.value_objects import (
    ParticipantsLimit,
    StreamUrl,
    WebinarSessionDuration,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Return ``.value``s of a ``StrEnum`` for ``sa.Enum.values_callable``.

    Mirrors the helper in ``models/product.py`` — kept local here
    to avoid a cross-module import inside infrastructure mapping.
    """
    return [member.value for member in enum_cls]


cohorts_table = sa.Table(
    "cohorts",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "webinar_id",
        sa.Uuid,
        sa.ForeignKey(
            "product_webinar_details.product_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    ),
    sa.Column(
        "host_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("name", sa.String(COHORT_NAME_MAX_LEN), nullable=True),
    sa.Column("max_participants", sa.Integer(), nullable=True),
    sa.Column("starts_on", sa.Date(), nullable=False),
    sa.Column("ends_on", sa.Date(), nullable=True),
    sa.Column(
        "enrollment_status",
        sa.Enum(
            CohortEnrollmentStatus,
            name="cohort_enrollment_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=CohortEnrollmentStatus.OPEN.value,
    ),
    sa.Column(
        "lifecycle_status",
        sa.Enum(
            CohortLifecycleStatus,
            name="cohort_lifecycle_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=CohortLifecycleStatus.UPCOMING.value,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_cohorts_webinar_id", "webinar_id"),
    sa.Index("ix_cohorts_host_id", "host_id"),
)


webinar_schedules_table = sa.Table(
    "webinar_schedules",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "cohort_id",
        sa.Uuid,
        sa.ForeignKey("cohorts.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "timezone",
        sa.String(IANA_TIMEZONE_MAX_LEN),
        nullable=False,
    ),
    sa.Column("starts_on", sa.Date(), nullable=False),
    sa.Column("ends_on", sa.Date(), nullable=True),
    sa.Column("rrule", sa.String(RRULE_MAX_LEN), nullable=False),
    sa.Column("duration_minutes", sa.Integer(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_webinar_schedules_cohort_id", "cohort_id"),
)


webinar_sessions_table = sa.Table(
    "webinar_sessions",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "cohort_id",
        sa.Uuid,
        sa.ForeignKey("cohorts.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "schedule_id",
        sa.Uuid,
        sa.ForeignKey("webinar_schedules.oid", ondelete="SET NULL"),
        nullable=True,
    ),
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
            WebinarSessionStatus,
            name="webinar_session_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=WebinarSessionStatus.SCHEDULED.value,
    ),
    sa.Column(
        "cancellation_reason",
        sa.String(CANCELLATION_REASON_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "stream_url",
        sa.String(SESSION_STREAM_URL_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "recording_url",
        sa.String(RECORDING_URL_MAX_LEN),
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
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.Index(
        "ix_webinar_sessions_cohort_id_starts_at",
        "cohort_id",
        "starts_at",
    ),
    sa.UniqueConstraint(
        "schedule_id",
        "original_starts_at",
        name="uq_webinar_sessions_schedule_original_starts",
    ),
)


_cohort_mapped = False
_schedule_mapped = False
_session_mapped = False


def map_cohort_table() -> None:
    """Apply imperative mapping from :class:`Cohort`."""
    global _cohort_mapped  # noqa: PLW0603
    if _cohort_mapped:
        return
    mapper_registry.map_imperatively(
        Cohort,
        cohorts_table,
        properties={
            "oid": cohorts_table.c.oid,
            "webinar_id": cohorts_table.c.webinar_id,
            "host_id": cohorts_table.c.host_id,
            "name": composite(
                CohortName.of_optional,
                cohorts_table.c.name,
            ),
            "max_participants": composite(
                ParticipantsLimit.of_optional,
                cohorts_table.c.max_participants,
            ),
            "starts_on": cohorts_table.c.starts_on,
            "ends_on": cohorts_table.c.ends_on,
            "enrollment_status": cohorts_table.c.enrollment_status,
            "lifecycle_status": cohorts_table.c.lifecycle_status,
            "created_at": cohorts_table.c.created_at,
        },
        column_prefix="_col_",
    )
    _cohort_mapped = True


def map_webinar_schedule_table() -> None:
    """Apply imperative mapping from :class:`WebinarSchedule`."""
    global _schedule_mapped  # noqa: PLW0603
    if _schedule_mapped:
        return
    mapper_registry.map_imperatively(
        WebinarSchedule,
        webinar_schedules_table,
        properties={
            "oid": webinar_schedules_table.c.oid,
            "cohort_id": webinar_schedules_table.c.cohort_id,
            "timezone": composite(
                IanaTimezone,
                webinar_schedules_table.c.timezone,
            ),
            "starts_on": webinar_schedules_table.c.starts_on,
            "ends_on": webinar_schedules_table.c.ends_on,
            "rrule": composite(
                RecurrenceRule,
                webinar_schedules_table.c.rrule,
            ),
            "duration_minutes": composite(
                WebinarSessionDuration,
                webinar_schedules_table.c.duration_minutes,
            ),
            "created_at": webinar_schedules_table.c.created_at,
        },
        column_prefix="_col_",
    )
    _schedule_mapped = True


def map_webinar_session_table() -> None:
    """Apply imperative mapping from :class:`WebinarSession`."""
    global _session_mapped  # noqa: PLW0603
    if _session_mapped:
        return
    mapper_registry.map_imperatively(
        WebinarSession,
        webinar_sessions_table,
        properties={
            "oid": webinar_sessions_table.c.oid,
            "cohort_id": webinar_sessions_table.c.cohort_id,
            "schedule_id": webinar_sessions_table.c.schedule_id,
            "original_starts_at": (webinar_sessions_table.c.original_starts_at),
            "starts_at": webinar_sessions_table.c.starts_at,
            "duration_minutes": composite(
                WebinarSessionDuration,
                webinar_sessions_table.c.duration_minutes,
            ),
            "status": webinar_sessions_table.c.status,
            "cancellation_reason": composite(
                CancellationReason.of_optional,
                webinar_sessions_table.c.cancellation_reason,
            ),
            "stream_url": composite(
                StreamUrl.of_optional,
                webinar_sessions_table.c.stream_url,
            ),
            "recording_url": composite(
                RecordingUrl.of_optional,
                webinar_sessions_table.c.recording_url,
            ),
            "created_at": webinar_sessions_table.c.created_at,
            "updated_at": webinar_sessions_table.c.updated_at,
        },
        column_prefix="_col_",
    )
    _session_mapped = True
