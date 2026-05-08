from enum import StrEnum


class CourseReleaseKind(StrEnum):
    """Semver-style bump kind chosen by the author at release time.

    Used to compute the next version from the previous release and
    to power refund-policy logic later (only ``major`` bumps open
    refund windows for active students).
    """

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
