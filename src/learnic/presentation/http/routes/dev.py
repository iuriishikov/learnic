"""Dev-only endpoints for local testing.

This router is registered in ``bootstrap.setup_routes`` **only when**
``AppConfig.environment == "development"``. In production the import
chain still runs (Python module load is harmless) but the router is
never attached to the FastAPI app — the routes physically do not
exist in prod, removing any risk of accidental activation by a
mis-set flag.

Use cases:

* ``POST /dev/wallet/topup`` — bypass the missing payment provider
  by crediting the caller's own wallet directly. Mirrors the eventual
  ``POST /users/me/wallet/topup`` shape so frontend code that drives
  the dev flow keeps working once the real endpoint lands.
* ``POST /dev/freezes/release-now`` — invoke the release worker
  inline. Lets a developer test the freeze → release transition
  without waiting for the next scheduler tick (typically 14 days in
  prod, configurable to seconds via env in dev).
"""

import uuid
from typing import Final

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.wallet.credit import (
    CreditWalletCommand,
    CreditWalletCommandHandler,
)
from learnic.application.commands.wallet.release_ripe import (
    ReleaseRipeFreezesCommandHandler,
)
from learnic.entities.wallet.constants import MAX_AMOUNT
from learnic.entities.wallet.enums import Currency, LedgerKind
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_WITH_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

dev_router = ErrorAwareRouter(
    prefix="/dev",
    tags=["Dev"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


class DevTopupSchema(BaseModel):
    """Body for ``POST /dev/wallet/topup``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"amount": 100_00}]},
    )

    amount: int = Field(
        description=(
            "Amount to credit in minor units (kopecks). Bounded by "
            f"MAX_AMOUNT = {MAX_AMOUNT}."
        ),
        examples=[100_00],
        ge=0,
        le=MAX_AMOUNT,
    )


class ReleaseSummarySchema(BaseModel):
    """Response for ``POST /dev/freezes/release-now``."""

    released: int = Field(
        description=(
            "Number of freeze entries released this run. Bounded by "
            "the handler's batch limit; rerun to drain a deeper backlog."
        ),
        examples=[3],
        ge=0,
    )


@dev_router.post(
    "/wallet/topup",
    summary="[dev] Credit the caller's own wallet directly",
    operation_id="devTopupMyWallet",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def dev_topup(
    request: Request,
    payload: DevTopupSchema,
    interactor: FromDishka[CreditWalletCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Credit ``amount`` minor units to the authenticated user's wallet.

    Each call generates a fresh idempotency key so repeated requests
    in dev keep adding money rather than coalescing — that's the
    convenient behaviour during testing. The handler under the hood
    is the same one that admin tooling and the future payment
    webhook will use.

    Args:
        request: Source of the access cookie.
        payload: ``{"amount": int}`` — amount in minor units.
        interactor: Injected CreditWalletCommand handler.
        auth: Injected authenticator.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        WalletNotFoundError: User has no wallet (system bug); HTTP 404.
        FieldError: ``MinorAmount`` invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CreditWalletCommand(
            user_id=ctx.user_id,
            amount=payload.amount,
            currency=Currency.RUB,
            source=LedgerKind.TOPUP,
            idempotency_key=f"dev-topup-{uuid.uuid4()}",
        ),
    )


@dev_router.post(
    "/freezes/release-now",
    summary="[dev] Run the release worker inline",
    operation_id="devReleaseRipeFreezes",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=ReleaseSummarySchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def dev_release_ripe(
    request: Request,
    interactor: FromDishka[ReleaseRipeFreezesCommandHandler],
    auth: FromDishka[Authenticator],
) -> ReleaseSummarySchema:
    """Invoke the release worker once, synchronously.

    Avoids the wait for the next ``taskiq scheduler`` tick. Useful
    when iterating on the freeze ⇆ release flow with a short
    ``FREEZE_TTL`` configured via env. Auth requires only that the
    caller is logged in — this is dev-only territory, not authorized
    by role.

    Args:
        request: Source of the access cookie.
        interactor: Injected ReleaseRipeFreezesCommand handler.
        auth: Injected authenticator.

    Returns:
        ``200 OK`` with ``{"released": int}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    await auth.authenticate(request)
    released = await interactor.run()
    return ReleaseSummarySchema(released=released)
