"""HTTP routes for the authenticated user's wallet.

Wallets are caller-scoped — there is no "list all wallets" or
"someone-else's wallet" endpoint by design. Per core rule 14, the
URL namespace for caller-scoped resources is ``/users/me/...``, so
both reads live under ``/users/me/wallet``.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.queries.wallet.get_ledger import (
    GetWalletLedgerQuery,
    GetWalletLedgerQueryHandler,
)
from learnic.application.queries.wallet.get_wallet import (
    GetWalletQuery,
    GetWalletQueryHandler,
)
from learnic.entities.wallet.enums import Currency, LedgerKind
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import AUTHENTICATED_MAP
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

me_wallet_router = ErrorAwareRouter(
    prefix="/users/me/wallet",
    tags=["Wallet"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


class WalletSchema(BaseModel):
    """Response for ``GET /users/me/wallet``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "currency": "RUB",
                    "available": 150_00,
                    "pending": 50_00,
                },
            ],
        },
    )

    currency: Currency = Field(
        description=(
            "Wallet's currency. The platform currently only supports "
            "`RUB`; the schema reserves the column for future markets."
        ),
        examples=["RUB"],
    )
    available: int = Field(
        description=(
            "Spendable balance in minor units (kopecks for RUB). "
            "Always non-negative."
        ),
        examples=[150_00],
        ge=0,
    )
    pending: int = Field(
        description=(
            "Sum of frozen funds in minor units. Becomes available "
            "once each freeze's `unfreeze_at` passes and the release "
            "worker processes it."
        ),
        examples=[50_00],
        ge=0,
    )


class LedgerEntrySchema(BaseModel):
    """Single ledger row in the history listing."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "0c2d3a44-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "kind": "purchase",
                    "delta": -500_00,
                    "reference_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "created_at": "2026-05-14T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID = Field(description="Ledger entry UUID.")
    kind: LedgerKind = Field(
        description=(
            "Why this entry was written. See the wallet section in the "
            "API description for the meaning of each value."
        ),
    )
    delta: int = Field(
        description=(
            "Signed change to `available` in minor units. Zero for "
            "informational events (`freeze`, `cancel_freeze`)."
        ),
    )
    reference_id: UUID | None = Field(
        description=(
            "Related entity: order id for `purchase`/`refund`, freeze "
            "id for `freeze`/`release`/`cancel_freeze`, `null` for "
            "free-standing `topup` / `adjustment`."
        ),
    )
    created_at: datetime = Field(
        description="UTC timestamp the entry was written at.",
    )


class WalletLedgerSchema(BaseModel):
    """Response for ``GET /users/me/wallet/ledger``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entries": [
                        {
                            "oid": "0c2d3a44-7b3a-4d2c-9d11-9d4f0a44b6c8",
                            "kind": "purchase",
                            "delta": -500_00,
                            "reference_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                            "created_at": "2026-05-14T10:00:00+00:00",
                        },
                    ],
                },
            ],
        },
    )

    entries: list[LedgerEntrySchema] = Field(
        description="Page of ledger rows, newest first.",
    )


@me_wallet_router.get(
    "/",
    summary="Get the current user's wallet",
    operation_id="getMyWallet",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=WalletSchema,
    error_map=AUTHENTICATED_MAP,
)
async def get_wallet(
    request: Request,
    interactor: FromDishka[GetWalletQueryHandler],
    auth: FromDishka[Authenticator],
) -> WalletSchema:
    """Return the caller's RUB wallet with available + pending totals.

    Args:
        request: Source of the access cookie.
        interactor: Injected GetWalletQuery handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``200 OK`` with :class:`WalletSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        WalletNotFoundError: User has no wallet (system bug — every
            user is backfilled at migration time); HTTP 404.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetWalletQuery(user_id=ctx.user_id, currency=Currency.RUB),
    )
    return WalletSchema(
        currency=view.currency,
        available=view.available,
        pending=view.pending,
    )


@me_wallet_router.get(
    "/ledger",
    summary="List the current user's wallet history",
    operation_id="getMyWalletLedger",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=WalletLedgerSchema,
    error_map=AUTHENTICATED_MAP,
)
async def get_ledger(
    request: Request,
    interactor: FromDishka[GetWalletLedgerQueryHandler],
    auth: FromDishka[Authenticator],
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="Page size (max MAX_LIMIT).",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset from the start of the descending ordering.",
    ),
) -> WalletLedgerSchema:
    """Return ledger entries for the caller's wallet, newest first.

    Args:
        request: Source of the access cookie.
        interactor: Injected GetWalletLedgerQuery handler.
        auth: Injected authenticator that validates the access cookie.
        limit: Maximum number of entries to return.
        offset: Number of entries to skip from the start.

    Returns:
        ``200 OK`` with :class:`WalletLedgerSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        WalletNotFoundError: User has no wallet; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    entries = await interactor.run(
        GetWalletLedgerQuery(
            user_id=ctx.user_id,
            currency=Currency.RUB,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return WalletLedgerSchema(
        entries=[
            LedgerEntrySchema(
                oid=entry.oid,
                kind=entry.kind,
                delta=entry.delta,
                reference_id=entry.reference_id,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
    )
