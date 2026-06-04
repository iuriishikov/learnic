from enum import StrEnum


class EnrollmentKind(StrEnum):
    """Discriminator for the polymorphic enrollment body.

    Each kind maps to exactly one subtype table in
    :mod:`learnic.infrastructure.persistence.models.enrollment` and
    one :class:`EnrollmentDetails` subclass — same pattern as
    :class:`NotificationKind`. Adding a new kind requires a new
    ``enrollment_<kind>`` subtype table and a matching
    ``EnrollmentDetails`` subclass.
    """

    NOTE = "note"


class EnrollmentStatus(StrEnum):
    """Lifecycle states for an enrollment.

    ``ACTIVE`` is the normal state. ``REVOKED`` is set by an
    author/admin action and removes access. Note-completion
    lives on ``NoteEnrollmentDetails.completed_at`` (orthogonal
    to access state) — a completed enrollment is still ACTIVE.
    """

    ACTIVE = "active"
    REVOKED = "revoked"
