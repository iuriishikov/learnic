"""Notification preferences HTTP routes.

The settings tab UI uses these to read and write the toggle
matrix:

- ``GET /users/me/notification-preferences`` — current matrix
  with defaults applied for users who haven't saved before.
- ``PUT /users/me/notification-preferences`` — full replacement
  of the push/email opt-in flags.

In-app delivery is not part of the wire format — it is always on
at the domain level and the UI renders the in-app toggle as
locked-on.
"""

from typing import Final

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict

from learnic.application.commands.notification_preferences.update import (
    UpdateNotificationPreferencesCommand,
    UpdateNotificationPreferencesCommandHandler,
)
from learnic.application.queries.notification_preferences.get_my import (
    GetMyNotificationPreferencesQuery,
    GetMyNotificationPreferencesQueryHandler,
)
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import AUTHENTICATED_MAP
from learnic.presentation.http.common.router import DishkaErrorAwareRoute


_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


router = ErrorAwareRouter(
    prefix="/users/me/notification-preferences",
    tags=["Notification preferences"],
    route_class=DishkaErrorAwareRoute,
)


class CategoryToggleSchema(BaseModel):
    """Per-category opt-in flags for one channel.

    Mirrors the rendered matrix: one bool per
    :class:`NotificationCategory`. The schema is intentionally
    flat (one field per category) so the OpenAPI shape is human
    readable in the docs and the diff in PRs is obvious when a
    new category is added.
    """

    invites: bool
    files: bool
    jobs: bool
    other: bool


class NotificationPreferencesSchema(BaseModel):
    """Full preferences matrix shipped over the wire.

    ``in_app`` is omitted on purpose — in-app delivery is always
    on. The frontend renders the in-app toggle as locked-on and
    never sends it.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "push": {
                        "invites": True,
                        "files": True,
                        "jobs": True,
                        "other": True,
                    },
                    "email": {
                        "invites": True,
                        "files": False,
                        "jobs": False,
                        "other": False,
                    },
                },
            ],
        },
    )

    push: CategoryToggleSchema
    email: CategoryToggleSchema

    @classmethod
    def from_entity(
        cls,
        entity: NotificationPreferences,
    ) -> "NotificationPreferencesSchema":
        return cls(
            push=_toggles_from_dict(entity.push),
            email=_toggles_from_dict(entity.email),
        )


def _toggles_from_dict(
    flags: dict[NotificationCategory, bool],
) -> CategoryToggleSchema:
    return CategoryToggleSchema(
        invites=flags.get(NotificationCategory.INVITES, False),
        files=flags.get(NotificationCategory.FILES, False),
        jobs=flags.get(NotificationCategory.JOBS, False),
        other=flags.get(NotificationCategory.OTHER, False),
    )


def _toggles_to_dict(
    schema: CategoryToggleSchema,
) -> dict[NotificationCategory, bool]:
    return {
        NotificationCategory.INVITES: schema.invites,
        NotificationCategory.FILES: schema.files,
        NotificationCategory.JOBS: schema.jobs,
        NotificationCategory.OTHER: schema.other,
    }


@router.get(
    "",
    summary="Return my notification preferences",
    operation_id="getMyNotificationPreferences",
    response_model=NotificationPreferencesSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def get_my(
    request: Request,
    interactor: FromDishka[GetMyNotificationPreferencesQueryHandler],
    auth: FromDishka[Authenticator],
) -> NotificationPreferencesSchema:
    """Return the caller's preferences with defaults applied.

    Args:
        request: Source of the access cookie.
        interactor: Injected get-my preferences query handler.
        auth: Injected authenticator.

    Returns:
        Preferences schema with full push/email matrices.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    entity = await interactor.run(
        GetMyNotificationPreferencesQuery(actor_id=ctx.user_id),
    )
    return NotificationPreferencesSchema.from_entity(entity)


@router.put(
    "",
    summary="Replace my notification preferences",
    operation_id="updateMyNotificationPreferences",
    response_model=NotificationPreferencesSchema,
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def update_my(
    request: Request,
    body: NotificationPreferencesSchema,
    interactor: FromDishka[UpdateNotificationPreferencesCommandHandler],
    auth: FromDishka[Authenticator],
) -> NotificationPreferencesSchema:
    """Replace the caller's preferences with the supplied matrix.

    Returns the saved matrix so the UI can confirm what was
    persisted in one round-trip.

    Args:
        request: Source of the access cookie.
        body: Full replacement matrix.
        interactor: Injected update preferences command handler.
        auth: Injected authenticator.

    Returns:
        Saved preferences schema.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateNotificationPreferencesCommand(
            actor_id=ctx.user_id,
            push=_toggles_to_dict(body.push),
            email=_toggles_to_dict(body.email),
        ),
    )
    return body
