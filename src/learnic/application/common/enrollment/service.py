from collections.abc import Mapping
from typing import Final, final

from learnic.application.common.enrollment.strategies import (
    EnrollmentStrategy,
    EnrollmentTarget,
)
from learnic.application.common.errors import AlreadyEnrolledError
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.enums import EnrollmentType
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.user.models import UserID


@final
class EnrollmentService:
    """Internal application API for enrolling a student in a product.

    Single entry point for **every** enrollment flow inside the
    app — self-enroll handlers, author-grant handlers,
    administrative scripts, scheduled provisioning tasks. **There
    is no public HTTP endpoint that calls this directly** —
    arbitrary-student grants are an admin operation; exposing
    them on the SPA side would let any caller create enrollments
    for arbitrary users. Type-specific HTTP handlers build the
    right :class:`EnrollmentTarget` from URL/auth context and
    delegate here.

    Dispatch is plug-in: the constructor receives a
    ``Mapping[EnrollmentType, EnrollmentStrategy]`` registered
    in :class:`EnrollmentStrategiesProvider` in ``ioc.py``, same
    pattern as :class:`NotifierService` with delivery channels.
    Adding a new product type only requires writing a strategy
    and adding it to that mapping — this service does not
    change.

    Owns the cross-type concerns:

    * "Already enrolled?" gate via :meth:`EnrollmentStrategy.find_existing`.
    * Transaction commit after the strategy stages everything.

    Type-specific work (parent validation, type-specific
    pre-conditions, side effects like cohort capacity flip)
    lives in the matching strategy.
    """

    def __init__(
        self,
        strategies: Mapping[EnrollmentType, EnrollmentStrategy],
        transaction: Transaction,
    ) -> None:
        self._strategies: Final = strategies
        self._transaction: Final = transaction

    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> EnrollmentID:
        strategy = self._strategies[target.enrollment_type]
        existing = await strategy.find_existing(student_id, target)
        if existing is not None:
            raise AlreadyEnrolledError(target.parent_id, student_id)
        enrollment = await strategy.enroll(student_id, target)
        await self._transaction.commit()
        return enrollment.oid
