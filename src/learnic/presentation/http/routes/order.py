"""HTTP routes for purchases and refunds.

Purchase is an action on a product, so it lives under
``/products/{product_id}/purchase`` (rule 14). The refund is
caller-scoped — only the buyer can refund their own order — and
lives under ``/users/me/orders/{order_id}/refund``.
"""

from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.order.purchase import (
    PurchaseProductCommand,
    PurchaseProductCommandHandler,
)
from learnic.application.commands.order.refund import (
    RefundPurchaseCommand,
    RefundPurchaseCommandHandler,
)
from learnic.entities.order.ids import OrderID
from learnic.entities.product.ids import ProductID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    PURCHASE_MAP,
    REFUND_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

product_purchase_router = ErrorAwareRouter(
    prefix="/products",
    tags=["Orders"],
    route_class=DishkaErrorAwareRoute,
)
me_orders_router = ErrorAwareRouter(
    prefix="/users/me/orders",
    tags=["Orders"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Product to purchase, as UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_ORDER_ID_PATH: Final = Path(
    description="Order to refund, as UUID.",
    examples=["0c2d3a44-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


class CreatedOrderSchema(BaseModel):
    """Response for ``POST /products/{id}/purchase``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "0c2d3a44-7b3a-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: OrderID = Field(
        description="UUID of the newly created order.",
    )


@product_purchase_router.post(
    "/{product_id}/purchase",
    summary="Purchase a product on behalf of the current user",
    operation_id="purchaseProduct",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedOrderSchema,
    error_map=PURCHASE_MAP,
)
async def purchase(
    request: Request,
    interactor: FromDishka[PurchaseProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedOrderSchema:
    """Charge the caller's wallet for the product price and create an order.

    The platform's commission and the author's share are split off the
    price and frozen on the platform / author wallet until their
    ``unfreeze_at`` passes (refund window). A successful response means
    the money has moved; granting access (enrollment) is a separate
    follow-up call until the enrollment subsystem is integrated with
    orders.

    Args:
        request: Source of the access cookie (also identifies the buyer).
        interactor: Injected PurchaseProductCommand handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Product to buy, from the URL path.

    Returns:
        ``201 Created`` with the new order's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: No such product; HTTP 404.
        ProductHasNoPriceError: Product has no price set yet; HTTP 409.
        InsufficientFundsError: Wallet does not cover the price;
            HTTP 409 with `available` + `required` in the body.
        FieldError: ``MinorAmount`` invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        PurchaseProductCommand(
            student_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    return CreatedOrderSchema(oid=oid)


@me_orders_router.post(
    "/{order_id}/refund",
    summary="Refund a paid order within the refund window",
    operation_id="refundMyOrder",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=REFUND_MAP,
)
async def refund(
    request: Request,
    interactor: FromDishka[RefundPurchaseCommandHandler],
    auth: FromDishka[Authenticator],
    order_id: UUID = _ORDER_ID_PATH,
) -> None:
    """Refund the caller's own order while both freezes are still pending.

    Refunds are allowed only when the author's and platform's freeze
    entries are both still in ``frozen`` state — i.e. before the
    release worker pays the money out. Once either is released the
    refund window is considered closed and the caller is redirected
    to support.

    Args:
        request: Source of the access cookie.
        interactor: Injected RefundPurchaseCommand handler.
        auth: Injected authenticator that validates the access cookie.
        order_id: Order to refund, from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        OrderActorMismatchError: Caller is not the buyer; HTTP 403.
        EntityNotFoundError: No such order; HTTP 404.
        OrderAlreadyRefundedError: Order is already refunded;
            HTTP 409.
        RefundWindowClosedError: At least one freeze has been
            released — refund no longer possible; HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RefundPurchaseCommand(
            actor_id=ctx.user_id,
            order_id=OrderID(order_id),
        ),
    )
