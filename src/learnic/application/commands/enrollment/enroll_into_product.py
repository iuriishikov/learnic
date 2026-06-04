from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    NoteEnrollmentTarget,
    EnrollmentTarget,
)
from learnic.application.common.errors import (
    CannotEnrollInPrivateProductError,
    CannotEnrollInUnpublishedProductError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
    ProductVisibility,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class EnrollIntoProductCommand:
    student_id: UserID
    product_id: ProductID


def _build_target(product: Product) -> EnrollmentTarget:
    """Return the strategy target matching ``product.type``.

    Explicit closed-set dispatch on :class:`ProductType` so adding a
    new variant trips :class:`AssertionError` at runtime — the
    sibling :class:`EnrollmentStrategy` registry already has a
    module-load fail-fast for its own variants, this mirrors it on
    the type → target side.
    """
    if product.type is ProductType.NOTE:
        return NoteEnrollmentTarget(product_id=product.oid)
    raise AssertionError(  # pragma: no cover
        f"No enrollment target for product type {product.type.value!r}",
    )


@final
class EnrollIntoProductCommandHandler:
    """Self-enroll the current student into any product.

    Single public self-enroll entry point. The HTTP layer hits this
    handler regardless of product type — kind-specific work
    (release pinning, capability check, etc.) lives further down
    in the strategy.

    Common policy enforced here:

    * Product must exist (HTTP 404 via
      :class:`EntityNotFoundError`).
    * Product status must be ``PUBLISHED`` (HTTP 409 via
      :class:`CannotEnrollInUnpublishedProductError`).
    * Product visibility must be ``PUBLIC`` — private products are
      invite-only and reachable solely through an accepted gift
      (HTTP 409 via :class:`CannotEnrollInPrivateProductError`).

    The product is loaded twice in the happy path — once here, once
    inside the strategy — but the second load hits the SQLAlchemy
    identity map and is effectively free. Keeping the gate here
    (instead of pushing it into the strategy) keeps the cross-kind
    policy in one place.
    """

    def __init__(
        self,
        service: EnrollmentService,
        product_gateway: ProductGateway,
    ) -> None:
        self._service: Final = service
        self._product_gateway: Final = product_gateway

    async def run(
        self,
        data: EnrollIntoProductCommand,
    ) -> EnrollmentID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.status is not ProductStatus.PUBLISHED:
            raise CannotEnrollInUnpublishedProductError(
                product_id=product.oid,
                status=product.status.value,
            )
        if product.visibility is ProductVisibility.PRIVATE:
            raise CannotEnrollInPrivateProductError(product_id=product.oid)
        return await self._service.enroll(
            student_id=data.student_id,
            target=_build_target(product),
        )
