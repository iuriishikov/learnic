from enum import StrEnum


class WebinarEnrollmentStatus(StrEnum):
    ACTIVE = "active"
    DROPPED = "dropped"
    COMPLETED = "completed"
    REFUNDED = "refunded"
