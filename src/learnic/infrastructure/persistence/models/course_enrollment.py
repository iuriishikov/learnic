from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.course_enrollment.value_objects import (
    ProgressPercent,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


course_enrollments_table = sa.Table(
    "course_enrollments",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
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
        "status",
        sa.Enum(
            CourseEnrollmentStatus,
            name="course_enrollment_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=CourseEnrollmentStatus.ACTIVE.value,
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
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey(
            "course_releases.oid",
            ondelete="RESTRICT",
            name="fk_course_enrollments_release_id",
        ),
        nullable=True,
    ),
    sa.UniqueConstraint(
        "product_id",
        "student_id",
        name="uq_course_enrollments_product_student",
    ),
    sa.Index("ix_course_enrollments_student_id", "student_id"),
    sa.Index("ix_course_enrollments_release_id", "release_id"),
)


_mapped = False


def map_course_enrollment_table() -> None:
    """Apply imperative mapping from :class:`CourseEnrollment`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        CourseEnrollment,
        course_enrollments_table,
        properties={
            "oid": course_enrollments_table.c.oid,
            "product_id": course_enrollments_table.c.product_id,
            "student_id": course_enrollments_table.c.student_id,
            "release_id": course_enrollments_table.c.release_id,
            "status": course_enrollments_table.c.status,
            "progress": composite(
                ProgressPercent,
                course_enrollments_table.c.progress_percent,
            ),
            "enrolled_at": course_enrollments_table.c.enrolled_at,
            "completed_at": course_enrollments_table.c.completed_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
