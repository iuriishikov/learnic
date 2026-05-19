from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    CourseEnrollmentTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GrantCourseEnrollmentCommand:
    actor_id: UserID
    student_id: UserID
    product_id: ProductID


@final
class GrantCourseEnrollmentCommandHandler:
    """Internal-only: actor enrols an arbitrary student in a course.

    **No public HTTP endpoint maps to this handler.** Granting an
    enrollment to another user is an admin/operational action —
    exposing it on the SPA would let any caller fabricate
    enrollments for arbitrary users. Internal callers (admin
    flows, batch provisioning, scheduled tasks) construct the
    command directly and invoke ``run``.

    Authorisation gate: actor must have ``MANAGE_RELEASES`` on
    the parent product (same permission family as
    ``CompleteEnrollmentCommandHandler`` and
    ``RefundEnrollmentCommandHandler`` for course-type
    enrollments).

    Target student existence is checked explicitly — for
    self-enroll the actor *is* the student so the check is
    implicit; here they are decoupled.

    Type-specific work (release pinning, capability check,
    "already enrolled?" gate, transaction commit) lives in
    :class:`EnrollmentService` and
    :class:`CourseEnrollmentStrategy`. This handler only adds
    the two grant-only concerns: actor authorisation and target
    existence.
    """

    def __init__(
        self,
        service: EnrollmentService,
        user_gateway: UserGateway,
        authorizer: Authorizer,
    ) -> None:
        self._service: Final = service
        self._user_gateway: Final = user_gateway
        self._authorizer: Final = authorizer

    async def run(
        self,
        data: GrantCourseEnrollmentCommand,
    ) -> EnrollmentID:
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        student = await self._user_gateway.with_id(data.student_id)
        if student is None:
            raise EntityNotFoundError(data.student_id)
        return await self._service.enroll(
            student_id=data.student_id,
            target=CourseEnrollmentTarget(product_id=data.product_id),
        )
