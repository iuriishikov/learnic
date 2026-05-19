from enum import StrEnum
from typing import Final

from learnic.entities.enrollment.enums import EnrollmentType


class EnrollmentCapability(StrEnum):
    """Operation an enrollment type may or may not support.

    Each :class:`EnrollmentType` declares its set of capabilities
    in :data:`ENROLLMENT_TYPE_CAPABILITIES`. Handlers gate
    type-specific operations through
    :meth:`Enrollment.require_supports` instead of spreading
    ``if enrollment.type is …`` checks across the codebase. Same
    pattern as :class:`ProductCapability`.
    """

    HAS_PROGRESS = "has_progress"
    """Tracks an asynchronous progress percent (0–100)."""

    HAS_RELEASE_PIN = "has_release_pin"
    """Pinned to a specific course release at signup time."""


ENROLLMENT_TYPE_CAPABILITIES: Final[
    dict[EnrollmentType, frozenset[EnrollmentCapability]]
] = {
    EnrollmentType.COURSE: frozenset(
        {
            EnrollmentCapability.HAS_PROGRESS,
            EnrollmentCapability.HAS_RELEASE_PIN,
        },
    ),
    EnrollmentType.WEBINAR: frozenset(),
}


# Fail-fast: any EnrollmentType without a capabilities row crashes
# at import time, not in a later authorization check.
_missing_types = set(EnrollmentType) - set(ENROLLMENT_TYPE_CAPABILITIES)
if _missing_types:
    raise RuntimeError(
        "ENROLLMENT_TYPE_CAPABILITIES is incomplete; missing entries for: "
        f"{sorted(t.value for t in _missing_types)}",
    )
