from enum import StrEnum


class CohortEnrollmentStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    FULL = "full"


class CohortLifecycleStatus(StrEnum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WebinarSessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
