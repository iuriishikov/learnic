"""Per-course storage-headroom query.

Tells the SPA how many more bytes can be uploaded into a given
course before the *course author's* plan cap is hit. Anchored on
the author so a collaborator opening an editor sees the same
number as the author would — they share one quota pool.
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.billing.ids import PlanCode
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetCourseStorageRemainingQuery:
    actor_id: UserID
    course_id: ProductID


@dataclass(slots=True, frozen=True)
class CourseStorageRemainingView:
    """Read-side projection for the course storage-headroom endpoint.

    All three numbers describe the *course author's* quota; the
    actor is irrelevant to the values themselves. ``remaining_bytes``
    is clamped to 0 — over-quota state (after a plan downgrade,
    say) reports as "0 free" rather than a negative value the SPA
    would have to handle.
    """

    plan_code: PlanCode
    storage_bytes_max: int
    storage_bytes_used: int
    storage_bytes_remaining: int


@final
class GetCourseStorageRemainingQueryHandler:
    """Resolve the course's author and report their quota headroom.

    The actor must hold ``EDIT_LESSONS`` on the course — same gate as
    the upload commands. Read-only: no advisory lock, the value is
    informational and re-validated by :meth:`EntitlementService.
    ensure_can_upload` at upload time.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        entitlement: EntitlementService,
    ) -> None:
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._entitlement: Final = entitlement

    async def run(
        self,
        data: GetCourseStorageRemainingQuery,
    ) -> CourseStorageRemainingView:
        product = await self._product_gateway.with_id(data.course_id)
        if product is None:
            raise EntityNotFoundError(data.course_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.course_id),
            Permission.EDIT_LESSONS,
        )
        snapshot = await self._entitlement.snapshot_for(product.author_id)
        return CourseStorageRemainingView(
            plan_code=snapshot.plan.code,
            storage_bytes_max=snapshot.plan.limits.storage_bytes_max,
            storage_bytes_used=snapshot.used_bytes,
            storage_bytes_remaining=snapshot.remaining_bytes,
        )
