from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.user_social_link.set_all import (
    SetUserSocialLinksCommand,
    SetUserSocialLinksCommandHandler,
    SocialLinkInput,
)
from learnic.application.queries.user_social_link.list_for_user import (
    ListUserSocialLinksQuery,
    ListUserSocialLinksQueryHandler,
)
from learnic.entities.user.constants import (
    SOCIAL_LINK_URL_MAX_LEN,
    SOCIAL_LINKS_MAX_COUNT,
)
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_WITH_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.application.common.errors import EntityNotFoundError

router = ErrorAwareRouter(
    prefix="/users/{user_id}/social-links",
    tags=["UserSocialLinks"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/social-links",
    tags=["UserSocialLinks"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]

_USER_ID_PATH: Final = Path(
    description="Target user's UUID.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)


class SocialLinkSchema(BaseModel):
    """A single social-network link on the user's public profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "kind": "linkedin",
                    "url": "https://www.linkedin.com/in/example",
                    "position": 0,
                },
            ],
        },
    )

    kind: SocialLinkKind = Field(
        description=(
            "Network identifier from `SocialLinkKind`. Drives icon "
            "selection on the public profile."
        ),
        examples=["linkedin", "github"],
    )
    url: str = Field(
        description=(
            "Profile URL. Must start with `http://` or `https://`. "
            f"Max length is {SOCIAL_LINK_URL_MAX_LEN} characters "
            "(`SOCIAL_LINK_URL_MAX_LEN`)."
        ),
        max_length=SOCIAL_LINK_URL_MAX_LEN,
        examples=["https://www.linkedin.com/in/example"],
    )
    position: int = Field(
        ge=0,
        description=(
            "Server-assigned 0-based position used to render the list "
            "in the order the user saved it."
        ),
        examples=[0],
    )


class SetSocialLinkSchema(BaseModel):
    """Single entry in the ``PUT /users/me/social-links`` payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"kind": "linkedin", "url": "https://www.linkedin.com/in/example"},
            ],
        },
    )

    kind: SocialLinkKind = Field(
        description=(
            "Network identifier from `SocialLinkKind`. The SPA picks "
            "one from the fixed list; choose `other` for misc URLs."
        ),
        examples=["linkedin"],
    )
    url: str = Field(
        description=(
            "Profile URL. Must start with `http://` or `https://`. "
            f"Max length is {SOCIAL_LINK_URL_MAX_LEN} characters."
        ),
        max_length=SOCIAL_LINK_URL_MAX_LEN,
        examples=["https://www.linkedin.com/in/example"],
    )


class SetSocialLinksSchema(BaseModel):
    """Body for `PUT /users/me/social-links` — atomic full replace."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "kind": "linkedin",
                            "url": "https://www.linkedin.com/in/example",
                        },
                        {"kind": "github", "url": "https://github.com/example"},
                    ],
                },
            ],
        },
    )

    items: list[SetSocialLinkSchema] = Field(
        description=(
            "Ordered list of social-link entries that will fully "
            "replace the user's current set. The order of the list "
            "becomes the persisted `position`. "
            f"Capped at {SOCIAL_LINKS_MAX_COUNT} entries "
            "(`SOCIAL_LINKS_MAX_COUNT`)."
        ),
        max_length=SOCIAL_LINKS_MAX_COUNT,
    )


@router.get(
    "",
    summary="List a user's social-network links",
    operation_id="listUserSocialLinks",
    response_model=list[SocialLinkSchema],
)
async def list_for_user(
    interactor: FromDishka[ListUserSocialLinksQueryHandler],
    user_id: UUID = _USER_ID_PATH,
) -> list[SocialLinkSchema]:
    """Return the user's social-link list, ordered by ``position``.

    Public — no authentication required — so the SPA can render the
    list on a stranger's public profile.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected list query handler.

    Returns:
        List of :class:`SocialLinkSchema`, possibly empty.
    """
    views = await interactor.run(
        ListUserSocialLinksQuery(user_id=UserID(user_id)),
    )
    return [
        SocialLinkSchema(kind=view.kind, url=view.url, position=view.position)
        for view in views
    ]


@me_router.put(
    "",
    summary="Replace the current user's social-network links",
    operation_id="setMySocialLinks",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
    },
)
async def set_all(
    request: Request,
    payload: SetSocialLinksSchema,
    interactor: FromDishka[SetUserSocialLinksCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Atomically replace every social-link row owned by the user.

    The supplied ``items`` order becomes the persisted ``position``
    so the SPA can reorder by sending the list back in a new order.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"items": [{"kind": ..., "url": ...}, ...]}``;
            capped at ``SOCIAL_LINKS_MAX_COUNT`` entries.
        interactor: Injected set-all command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: A `SocialLinkUrl` VO invariant was violated, or
            the list exceeds the per-user cap; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        SetUserSocialLinksCommand(
            user_id=ctx.user_id,
            items=tuple(
                SocialLinkInput(kind=item.kind, url=item.url) for item in payload.items
            ),
        ),
    )
