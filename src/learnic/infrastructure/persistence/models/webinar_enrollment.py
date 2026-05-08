from enum import StrEnum

import sqlalchemy as sa

from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.models import WebinarEnrollment
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


webinar_enrollments_table = sa.Table(
    "webinar_enrollments",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "cohort_id",
        sa.Uuid,
        sa.ForeignKey("cohorts.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "student_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "status",
        sa.Enum(
            WebinarEnrollmentStatus,
            name="webinar_enrollment_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=WebinarEnrollmentStatus.ACTIVE.value,
    ),
    sa.Column(
        "enrolled_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "cohort_id",
        "student_id",
        name="uq_webinar_enrollments_cohort_student",
    ),
    sa.Index("ix_webinar_enrollments_student_id", "student_id"),
)


_mapped = False


def map_webinar_enrollment_table() -> None:
    """Apply imperative mapping from :class:`WebinarEnrollment`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        WebinarEnrollment,
        webinar_enrollments_table,
        properties={
            "oid": webinar_enrollments_table.c.oid,
            "cohort_id": webinar_enrollments_table.c.cohort_id,
            "student_id": webinar_enrollments_table.c.student_id,
            "status": webinar_enrollments_table.c.status,
            "enrolled_at": webinar_enrollments_table.c.enrolled_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
