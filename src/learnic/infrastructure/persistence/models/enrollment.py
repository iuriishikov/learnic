from enum import StrEnum

import sqlalchemy as sa

from learnic.entities.enrollment.enums import (
    EnrollmentKind,
    EnrollmentStatus,
)
from learnic.entities.enrollment.models import Enrollment
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


# Common enrollment row — the discriminator + state machine fields.
# ``product_id`` lives on the base row so the
# UNIQUE(product_id, student_id) constraint sits directly on the
# enrollments table (Postgres unique constraints span one table
# only). The kind-specific subtype tables no longer need to
# denormalise ``product_id``.
enrollments_table = sa.Table(
    "enrollments",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "kind",
        sa.Enum(
            EnrollmentKind,
            name="enrollment_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
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
        "status",
        sa.Enum(
            EnrollmentStatus,
            name="enrollment_status",
            values_callable=_enum_values,
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
    sa.UniqueConstraint(
        "product_id",
        "student_id",
        name="uq_enrollments_product_student",
    ),
    sa.Index("ix_enrollments_student_id", "student_id"),
    sa.Index("ix_enrollments_kind_status", "kind", "status"),
)


# Course-specific 1:1 subtype row. PK == FK enrollments.oid so the
# row dies with its parent. ``product_id`` / ``student_id`` are
# NOT denormalised here — they live on the parent enrollments row,
# which now carries the UNIQUE(product_id, student_id) constraint.
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
    sa.Index("ix_enrollment_course_details_release_id", "release_id"),
)


_enrollment_mapped = False


def map_enrollment_table() -> None:
    """Apply imperative mapping for :class:`Enrollment`.

    Only the base columns are mapped here. The polymorphic
    ``details`` field is intentionally NOT mapped — the gateway
    inserts the right subtype row alongside the parent and loads
    it back out-of-band based on ``kind`` (same pattern as
    :class:`Notification` + :class:`NotificationDetails`).
    """
    global _enrollment_mapped  # noqa: PLW0603
    if _enrollment_mapped:
        return
    mapper_registry.map_imperatively(
        Enrollment,
        enrollments_table,
        properties={
            "oid": enrollments_table.c.oid,
            "kind": enrollments_table.c.kind,
            "product_id": enrollments_table.c.product_id,
            "student_id": enrollments_table.c.student_id,
            "status": enrollments_table.c.status,
            "enrolled_at": enrollments_table.c.enrolled_at,
        },
        column_prefix="_col_",
    )
    _enrollment_mapped = True
