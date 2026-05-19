from collections.abc import Mapping
from typing import Final, final

from learnic.application.common.enrollment.strategies import (
    CourseEnrollmentTarget,
    EnrollmentStrategy,
    EnrollmentTarget,
)
from learnic.application.common.errors import AlreadyEnrolledError
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.product.ids import ProductID
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
    for arbitrary users. Kind-specific HTTP handlers build the
    right :class:`EnrollmentTarget` from URL/auth context and
    delegate here.

    Dispatch is plug-in: the constructor receives a
    ``Mapping[EnrollmentKind, EnrollmentStrategy]`` registered
    in :class:`EnrollmentStrategiesProvider` in ``ioc.py``, same
    pattern as :class:`NotifierService` with delivery channels.
    Adding a new product kind only requires writing a strategy
    and adding it to that mapping — this service does not
    change.

    Owns the cross-kind concerns:

    * "Already enrolled?" gate via :meth:`EnrollmentStrategy.find_existing`.
    * Transaction commit after the strategy stages everything.

    Kind-specific work (parent validation, kind-specific
    pre-conditions) lives in the matching strategy.
    """

    def __init__(
        self,
        strategies: Mapping[EnrollmentKind, EnrollmentStrategy],
        transaction: Transaction,
    ) -> None:
        self._strategies: Final = strategies
        self._transaction: Final = transaction

    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> EnrollmentID:
        strategy = self._strategies[target.enrollment_kind]
        existing = await strategy.find_existing(student_id, target)
        if existing is not None:
            raise AlreadyEnrolledError(target.parent_id, student_id)
        enrollment = await strategy.enroll(student_id, target)
        await self._transaction.commit()
        return enrollment.oid

    async def enroll_in_course(
        self,
        student_id: UserID,
        product_id: ProductID,
    ) -> EnrollmentID:
        """Convenience: enroll a student into a course product.

        Thin wrapper that builds the :class:`CourseEnrollmentTarget`
        so internal callers (other application services, scripts,
        admin grants) do not have to import strategy targets.
        """
        return await self.enroll(
            student_id=student_id,
            target=CourseEnrollmentTarget(product_id=product_id),
        )
