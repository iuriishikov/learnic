from enum import StrEnum


class CourseEnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    REFUNDED = "refunded"
