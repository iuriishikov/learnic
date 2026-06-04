from enum import StrEnum
from typing import Final

from learnic.entities.enrollment.enums import EnrollmentKind


class EnrollmentCapability(StrEnum):
    """Operation an enrollment kind may or may not support.

    Each :class:`EnrollmentKind` declares its set of capabilities
    in :data:`ENROLLMENT_KIND_CAPABILITIES`. Handlers gate
    kind-specific operations through
    :meth:`Enrollment.require_supports` instead of spreading
    ``if enrollment.kind is …`` checks across the codebase. Same
    pattern as :class:`ProductCapability`.
    """

    HAS_PROGRESS = "has_progress"
    """Tracks an asynchronous progress percent (0–100)."""

    HAS_RELEASE_PIN = "has_release_pin"
    """Pinned to a specific note release at signup time."""


ENROLLMENT_KIND_CAPABILITIES: Final[
    dict[EnrollmentKind, frozenset[EnrollmentCapability]]
] = {
    EnrollmentKind.NOTE: frozenset(
        {
            EnrollmentCapability.HAS_PROGRESS,
            EnrollmentCapability.HAS_RELEASE_PIN,
        },
    ),
}


# Fail-fast: any EnrollmentKind without a capabilities row crashes
# at import time, not in a later authorization check.
_missing_kinds = set(EnrollmentKind) - set(ENROLLMENT_KIND_CAPABILITIES)
if _missing_kinds:
    raise RuntimeError(
        "ENROLLMENT_KIND_CAPABILITIES is incomplete; missing entries for: "
        f"{sorted(k.value for k in _missing_kinds)}",
    )
