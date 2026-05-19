from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.enrollment.course_details import CourseDetails
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.enrollment.webinar_details import WebinarDetails
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


# Common enrollment row — the discriminator + state machine fields.
# Student is referenced here AND denormalised into each side-detail
# table so the (parent_id, student_id) uniqueness constraints can
# stay declarative (Postgres unique constraints span one table only).
enrollments_table = sa.Table(
    "enrollments",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "type",
        sa.Enum(
            EnrollmentType,
            name="enrollment_type",
            values_callable=_enum_values,
        ),
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
            EnrollmentStatus,
            name="enrollment_status",
            values_callable=_enum_values,
            # NOTE: shares the prior course_enrollment_status name
            # in upgrade migrations to avoid an extra PG enum drop
            # + create cycle; see the data migration for details.
        ),
        nullable=False,
        server_default=EnrollmentStatus.ACTIVE.value,
    ),
    sa.Column(
        "enrolled_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_enrollments_student_id", "student_id"),
    sa.Index("ix_enrollments_type_status", "type", "status"),
)


# Course-specific 1:1 side row. PK == FK enrollments.oid so the row
# dies with its parent. Includes denormalised student_id so the
# UNIQUE(product_id, student_id) constraint stays in DB.
enrollment_course_details_table = sa.Table(
    "enrollment_course_details",
    mapper_registry.metadata,
    sa.Column(
        "enrollment_id",
        sa.Uuid,
        sa.ForeignKey("enrollments.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "student_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey(
            "course_releases.oid",
            ondelete="RESTRICT",
            name="fk_enrollment_course_details_release_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "progress_percent",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Column(
        "completed_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    sa.UniqueConstraint(
        "product_id",
        "student_id",
        name="uq_enrollment_course_details_product_student",
    ),
    sa.Index("ix_enrollment_course_details_release_id", "release_id"),
)


# Webinar-specific 1:1 side row. PK == FK enrollments.oid.
enrollment_webinar_details_table = sa.Table(
    "enrollment_webinar_details",
    mapper_registry.metadata,
    sa.Column(
        "enrollment_id",
        sa.Uuid,
        sa.ForeignKey("enrollments.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
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
    sa.UniqueConstraint(
        "cohort_id",
        "student_id",
        name="uq_enrollment_webinar_details_cohort_student",
    ),
)


_enrollment_mapped = False
_course_details_mapped = False
_webinar_details_mapped = False


def map_enrollment_table() -> None:
    """Apply imperative mapping from :class:`Enrollment`.

    Only the common columns are mapped here. ``course_details``
    and ``webinar_details`` are left out of the imperative
    mapping intentionally — the gateway loads them out-of-band
    based on ``type`` (same pattern as ``Product`` /
    ``WebinarDetails``). The class-level ``= None`` defaults on
    those attributes keep them readable on freshly hydrated
    instances.
    """
    global _enrollment_mapped  # noqa: PLW0603
    if _enrollment_mapped:
        return
    mapper_registry.map_imperatively(
        Enrollment,
        enrollments_table,
        properties={
            "oid": enrollments_table.c.oid,
            "type": enrollments_table.c.type,
            "student_id": enrollments_table.c.student_id,
            "status": enrollments_table.c.status,
            "enrolled_at": enrollments_table.c.enrolled_at,
        },
        column_prefix="_col_",
    )
    _enrollment_mapped = True


def map_enrollment_course_details_table() -> None:
    global _course_details_mapped  # noqa: PLW0603
    if _course_details_mapped:
        return
    mapper_registry.map_imperatively(
        CourseDetails,
        enrollment_course_details_table,
        properties={
            "oid": enrollment_course_details_table.c.enrollment_id,
            "product_id": enrollment_course_details_table.c.product_id,
            "student_id": enrollment_course_details_table.c.student_id,
            "release_id": enrollment_course_details_table.c.release_id,
            "progress": composite(
                ProgressPercent,
                enrollment_course_details_table.c.progress_percent,
            ),
            "completed_at": enrollment_course_details_table.c.completed_at,
        },
        column_prefix="_col_",
    )
    _course_details_mapped = True


def map_enrollment_webinar_details_table() -> None:
    global _webinar_details_mapped  # noqa: PLW0603
    if _webinar_details_mapped:
        return
    mapper_registry.map_imperatively(
        WebinarDetails,
        enrollment_webinar_details_table,
        properties={
            "oid": enrollment_webinar_details_table.c.enrollment_id,
            "cohort_id": enrollment_webinar_details_table.c.cohort_id,
            "student_id": enrollment_webinar_details_table.c.student_id,
        },
        column_prefix="_col_",
    )
    _webinar_details_mapped = True
