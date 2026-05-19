from enum import StrEnum


class EnrollmentType(StrEnum):
    """Discriminator for the two enrollment shapes.

    Mirrors the :class:`ProductType` split — every enrollment is
    either tied to a course product (``COURSE``) or to a webinar
    cohort (``WEBINAR``). The type drives which side-detail row
    exists and which capabilities the enrollment supports.
    """

    COURSE = "course"
    WEBINAR = "webinar"


class EnrollmentStatus(StrEnum):
    """Lifecycle states shared by both enrollment types.

    Webinar-specific ``DROPPED`` does not exist: dropping a
    webinar enrollment goes through the refund flow instead. A
    student who wants to walk away without payment reversal is
    not modelled — that would require a separate `CANCELLED`
    status with explicit semantics.
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    REFUNDED = "refunded"
