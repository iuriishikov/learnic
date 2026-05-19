"""Per-product-type enrollment policies (strategy pattern).

Adding a new :class:`EnrollmentType` follows the same shape as
adding a notification channel (``NotificationChannelsProvider``
in ``ioc.py``):

1. Add a new :class:`EnrollmentTarget` variant describing what
   parent the enrollment ties to (a ``ProductID`` for courses,
   a ``CohortID`` for webinars, …). Each variant declares its
   ``enrollment_type`` as a ``ClassVar`` so the dispatcher does
   not branch on ``isinstance``.

2. Implement an :class:`EnrollmentStrategy` for the new type
   (alongside ``CourseEnrollmentStrategy`` /
   ``WebinarEnrollmentStrategy``). The strategy owns every
   type-specific concern — parent validation, type-specific
   pre-conditions (release pinning, cohort capacity), the
   ``Enrollment.create_*`` factory, persisting both the parent
   row and the side-detail row.

3. Add the new type to :data:`_DECLARED_STRATEGIES` below so the
   module-level fail-fast assertion crashes on import if anyone
   later adds a new :class:`EnrollmentType` without a matching
   strategy. Same pattern as
   ``ENROLLMENT_TYPE_CAPABILITIES``.

4. Register the strategy in
   ``EnrollmentStrategiesProvider`` in ``ioc.py`` and add it to
   the ``Mapping[EnrollmentType, EnrollmentStrategy]`` it
   provides. The runtime registry refuses to start if it does
   not cover every :class:`EnrollmentType` variant.

Cross-type concerns (the actor-side "is already enrolled?"
check, the surrounding transaction commit, optional actor
authorisation) live one layer up in
:class:`EnrollmentService` so each strategy stays focused on
its single product type.
"""

from dataclasses import dataclass
from typing import ClassVar, Final, Protocol, TypeAlias
from uuid import UUID

from learnic.entities.cohort.ids import CohortID
from learnic.entities.enrollment.enums import EnrollmentType
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CourseEnrollmentTarget:
    """Course-type enrollment target. Ties to a course product."""

    enrollment_type: ClassVar[EnrollmentType] = EnrollmentType.COURSE
    product_id: ProductID

    @property
    def parent_id(self) -> UUID:
        return self.product_id


@dataclass(slots=True, frozen=True)
class WebinarEnrollmentTarget:
    """Webinar-type enrollment target. Ties to a specific cohort."""

    enrollment_type: ClassVar[EnrollmentType] = EnrollmentType.WEBINAR
    cohort_id: CohortID

    @property
    def parent_id(self) -> UUID:
        return self.cohort_id


EnrollmentTarget: TypeAlias = (
    CourseEnrollmentTarget | WebinarEnrollmentTarget
)


class EnrollmentStrategy(Protocol):
    """Per-product-type enrollment policy.

    Owns every concern that differs by ``EnrollmentType``:
    parent existence + status checks, type-specific
    pre-conditions, constructing the :class:`Enrollment` with
    its side details, persisting both rows. The surrounding
    transaction commit lives in :class:`EnrollmentService` so
    the strategy stays focused on its single product type.

    Strategies may also mutate adjacent entities loaded through
    a gateway (e.g. flip a cohort to ``FULL`` when capacity is
    hit) — those mutations are picked up by the unit of work
    and persisted by the same commit.
    """

    enrollment_type: ClassVar[EnrollmentType]

    async def find_existing(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment | None:
        """Return the existing enrollment if the student is already
        enrolled in this target, else ``None``. Used by the service
        to enforce the cross-type ``AlreadyEnrolled`` invariant
        without each strategy having to raise it.
        """
        ...

    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment:
        """Validate type-specific pre-conditions, construct the
        :class:`Enrollment` + side-detail entities and register
        them with the unit of work. Returns the new (unflushed)
        :class:`Enrollment`. Raises domain errors on validation
        failure (e.g. ``CannotEnrollInUnreleasedCourseError``,
        ``CohortFullError``).
        """
        ...


# Fail-fast contract. Whenever a new ``EnrollmentType`` is added,
# its strategy must also be declared here — otherwise this module
# refuses to import and the failure surfaces immediately, not at
# the first runtime ``KeyError`` deep inside a request.
_DECLARED_STRATEGIES: Final[frozenset[EnrollmentType]] = frozenset(
    {
        EnrollmentType.COURSE,
        EnrollmentType.WEBINAR,
    },
)


def _check_contract() -> None:
    missing = set(EnrollmentType) - _DECLARED_STRATEGIES
    if missing:
        raise RuntimeError(
            "EnrollmentStrategy contract incomplete; add a strategy "
            "for: "
            f"{sorted(t.value for t in missing)}",
        )


_check_contract()
