from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.user.avatar.remove import (
    RemoveUserAvatarCommand,
    RemoveUserAvatarCommandHandler,
)
from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommand,
    SetUserAvatarCommandHandler,
)
from learnic.application.commands.user.change_description import (
    ChangeUserDescriptionCommand,
    ChangeUserDescriptionCommandHandler,
)
from learnic.application.commands.user.change_first_name import (
    ChangeUserFirstNameCommand,
    ChangeUserFirstNameCommandHandler,
)
from learnic.application.commands.user.change_last_name import (
    ChangeUserLastNameCommand,
    ChangeUserLastNameCommandHandler,
)
from learnic.application.commands.user.change_patronymic import (
    ChangeUserPatronymicCommand,
    ChangeUserPatronymicCommandHandler,
)
from learnic.application.commands.user.change_portfolio_url import (
    ChangeUserPortfolioUrlCommand,
    ChangeUserPortfolioUrlCommandHandler,
)
from learnic.application.commands.user.change_public_email import (
    ChangeUserPublicEmailCommand,
    ChangeUserPublicEmailCommandHandler,
)
from learnic.application.commands.user.change_website_url import (
    ChangeUserWebsiteUrlCommand,
    ChangeUserWebsiteUrlCommandHandler,
)
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommand,
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommand,
    SetUserCoverCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    UserAvatarNotFoundError,
    UserCoverNotFoundError,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.common.statistics.collector import (
    StatisticsCollector,
)
from learnic.entities.statistic.models import Statistic
from learnic.application.queries.product.get_by_user import (
    GetUserProductsQuery,
    GetUserProductsQueryHandler,
)
from learnic.application.queries.user.get import (
    GetUserQuery,
    GetUserQueryHandler,
)
from learnic.application.queries.user.get_avatar import (
    GetUserAvatarQuery,
    GetUserAvatarQueryHandler,
)
from learnic.application.queries.user.get_cover import (
    GetUserCoverQuery,
    GetUserCoverQueryHandler,
)
from learnic.application.queries.user.search import (
    SearchUsersQuery,
    SearchUsersQueryHandler,
)
from learnic.entities.user.constants import (
    DESCRIPTION_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PATRONYMIC_MAX_LEN,
    PORTFOLIO_URL_MAX_LEN,
    PUBLIC_EMAIL_MAX_LEN,
    WEBSITE_URL_MAX_LEN,
)
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
    USER_AVATAR_NOT_FOUND_RULE,
    USER_COVER_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import (
    FileSchema,
    UserSchema,
    UserSummarySchema,
)
# Importing a sibling-router's response model is the deliberate trade-off:
# the `Products` aggregate owns `ProductSchema`, but the public-profile
# rail returns it from a user-prefixed URL (per the URL-hierarchy rule).
# Cross-importing the schema is cheaper than duplicating it.
from learnic.presentation.http.routes.product import ProductSchema
from learnic.presentation.http.common.uploads import read_image_upload

router = ErrorAwareRouter(
    prefix="/users",
    tags=["Users"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


class ChangeFirstNameSchema(BaseModel):
    """Body for `PUT /users/me/first-name`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": "Ada"}]},
    )

    value: str = Field(
        description=(
            "New first name. Required, non-empty after trimming. "
            f"Max length is {FIRST_NAME_MAX_LEN} characters "
            "(`FIRST_NAME_MAX_LEN`)."
        ),
        min_length=1,
        max_length=FIRST_NAME_MAX_LEN,
        examples=["Ada"],
    )


class ChangeLastNameSchema(BaseModel):
    """Body for `PUT /users/me/last-name`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": "Lovelace"}]},
    )

    value: str = Field(
        description=(
            "New last name. Required, non-empty after trimming. "
            f"Max length is {LAST_NAME_MAX_LEN} characters "
            "(`LAST_NAME_MAX_LEN`)."
        ),
        min_length=1,
        max_length=LAST_NAME_MAX_LEN,
        examples=["Lovelace"],
    )


class ChangePatronymicSchema(BaseModel):
    """Body for `PUT /users/me/patronymic`.

    Pass `null` to clear the field.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": "Augusta"}, {"value": None}],
        },
    )

    value: str | None = Field(
        description=(
            "New patronymic, or `null` to clear it. "
            f"Max length is {PATRONYMIC_MAX_LEN} characters "
            "(`PATRONYMIC_MAX_LEN`)."
        ),
        max_length=PATRONYMIC_MAX_LEN,
        examples=["Augusta", None],
    )


class ChangeWebsiteUrlSchema(BaseModel):
    """Body for `PUT /users/me/website-url`. `null` clears the field."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"value": "https://example.com"},
                {"value": None},
            ],
        },
    )

    value: str | None = Field(
        description=(
            "New personal-website URL, or `null` to clear it. Must "
            "start with `http://` or `https://`. Max length is "
            f"{WEBSITE_URL_MAX_LEN} characters (`WEBSITE_URL_MAX_LEN`)."
        ),
        max_length=WEBSITE_URL_MAX_LEN,
        examples=["https://example.com", None],
    )


class ChangePortfolioUrlSchema(BaseModel):
    """Body for `PUT /users/me/portfolio-url`. `null` clears the field."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"value": "https://dribbble.com/example"},
                {"value": None},
            ],
        },
    )

    value: str | None = Field(
        description=(
            "New portfolio URL, or `null` to clear it. Must start with "
            "`http://` or `https://`. Max length is "
            f"{PORTFOLIO_URL_MAX_LEN} characters (`PORTFOLIO_URL_MAX_LEN`)."
        ),
        max_length=PORTFOLIO_URL_MAX_LEN,
        examples=["https://dribbble.com/example", None],
    )


class ChangePublicEmailSchema(BaseModel):
    """Body for `PUT /users/me/public-email`. `null` clears the field."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"value": "hello@example.com"},
                {"value": None},
            ],
        },
    )

    value: str | None = Field(
        description=(
            "Public contact email shown on the profile, or `null` to "
            "clear it. Distinct from the login email — there is no "
            "verification flow. Must contain `@`. Max length is "
            f"{PUBLIC_EMAIL_MAX_LEN} characters (`PUBLIC_EMAIL_MAX_LEN`)."
        ),
        max_length=PUBLIC_EMAIL_MAX_LEN,
        examples=["hello@example.com", None],
    )


class ChangeDescriptionSchema(BaseModel):
    """Body for `PUT /users/me/description`.

    Pass `null` to clear the field. Incoming HTML is sanitized
    server-side; unsafe tags and attributes are stripped before the
    value reaches the domain.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"value": "<p>Hello world.</p>"},
                {"value": None},
            ],
        },
    )

    value: str | None = Field(
        description=(
            "New profile description as HTML, or `null` to clear it. "
            f"Max length is {DESCRIPTION_MAX_LEN} characters "
            "(`DESCRIPTION_MAX_LEN`) measured **after** sanitization. "
            "The server strips unsafe tags/attrs before storage."
        ),
        max_length=DESCRIPTION_MAX_LEN,
        examples=["<p>Hello world.</p>", None],
    )


_USER_ID_PATH: Final = Path(
    description="Target user's UUID.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)

_SEARCH_QUERY_MAX_LEN: Final = 200


@router.get(
    "/search",
    summary="Search registered users by name fields",
    operation_id="searchUsers",
    response_model=list[UserSummarySchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def search(
    request: Request,
    interactor: FromDishka[SearchUsersQueryHandler],
    auth: FromDishka[Authenticator],
    q: str = Query(
        description=(
            "Free-text query. Whitespace-tokenized; each token must "
            "match (case-insensitive substring) at least one of "
            "`first_name` / `last_name` / `patronymic`. Tokens combine "
            "with AND so multiple words narrow the result. Empty / "
            "whitespace-only inputs return an empty list."
        ),
        min_length=0,
        max_length=_SEARCH_QUERY_MAX_LEN,
        examples=["Ada", "Иван Иванов"],
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset (rows to skip), `>= 0`.",
        examples=[0],
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`)."),
        examples=[20],
    ),
) -> list[UserSummarySchema]:
    """Return users whose name fields match every token of ``q``.

    Used by the team-invite UI to look up registered users by their
    Russian / Latin name fields. Returns the same lightweight
    projection across all callers — ``email`` and ``description``
    stay private; only ``avatar_url`` is resolved to a presigned URL
    for inline display. Sorted by ``last_name``, ``first_name``,
    ``oid`` for stable pagination.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected search query handler.
        auth: Injected authenticator that validates the access cookie.
        q: Free-text query against name fields.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        List of :class:`UserSummarySchema`, possibly empty.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    await auth.authenticate(request)
    views = await interactor.run(
        SearchUsersQuery(
            query=q,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [UserSummarySchema.from_view(view) for view in views]


@router.get(
    "/{user_id}",
    summary="Get a user's public profile",
    operation_id="getUserById",
    response_model=UserSchema,
    dependencies=_AUTH_SECURITY,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get(
    request: Request,
    interactor: FromDishka[GetUserQueryHandler],
    auth: FromDishka[Authenticator],
    stats: FromDishka[StatisticsCollector],
    user_id: UUID = _USER_ID_PATH,
) -> UserSchema:
    """Return a user by id with presigned URLs for avatar/cover.

    Authentication is **optional**: anonymous callers receive the
    same payload as signed-in ones. A valid access cookie has one
    extra effect — the call records a ``profile_view`` statistic
    attributed to the caller (skipped when the caller is the
    profile owner). A missing or stale cookie degrades silently
    to the anonymous path, so a logged-out browser never sees a
    401 here.

    Args:
        request: Source of the (optional) access cookie and
            ``Referer`` header used for the stat row.
        interactor: Injected get-user query handler.
        auth: Injected authenticator; consulted via
            :meth:`Authenticator.authenticate_optional`.
        stats: Injected statistics collector; failures are
            swallowed by the collector implementation.
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        ``UserSchema`` with profile fields and short-lived presigned
        URLs for avatar/cover (``null`` if not set). ``email`` is
        deliberately omitted.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    target_id = UserID(user_id)
    view = await interactor.run(GetUserQuery(oid=target_id))
    ctx = await auth.authenticate_optional(request)
    if ctx is not None and ctx.user_id != target_id:
        await stats.record(
            Statistic.for_profile_view(
                actor_id=ctx.user_id,
                target_user_id=target_id,
                referrer=request.headers.get("referer"),
            ),
        )
    return UserSchema.from_view(view)


@router.get(
    "/{user_id}/avatar",
    summary="Get a user's avatar (redirect)",
    operation_id="getUserAvatar",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses={
        status.HTTP_302_FOUND: {
            "description": (
                "Redirect to a short-lived presigned storage URL for "
                "the avatar image. Browser clients will follow the "
                "redirect transparently; non-browser clients should "
                "either follow redirects or read the `Location` "
                "header without following."
            ),
            "headers": {
                "Location": {
                    "description": ("Presigned URL pointing at the avatar object."),
                    "schema": {"type": "string", "format": "uri"},
                },
            },
        },
    },
    error_map={
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
        UserAvatarNotFoundError: USER_AVATAR_NOT_FOUND_RULE,
    },
)
async def get_avatar(
    interactor: FromDishka[GetUserAvatarQueryHandler],
    user_id: UUID = _USER_ID_PATH,
) -> RedirectResponse:
    """Return the user's avatar as a redirect to presigned storage.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected get-avatar query handler.

    Returns:
        ``302 Found`` ``RedirectResponse`` to the short-lived presigned
        storage URL for the avatar image.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404 via
            ``ENTITY_NOT_FOUND_RULE``.
        UserAvatarNotFoundError: The user exists but has no avatar
            attached; HTTP 404 via ``USER_AVATAR_NOT_FOUND_RULE``.
    """
    output = await interactor.run(GetUserAvatarQuery(oid=UserID(user_id)))
    return RedirectResponse(
        url=output.url,
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/{user_id}/cover",
    summary="Get a user's cover (redirect)",
    operation_id="getUserCover",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses={
        status.HTTP_302_FOUND: {
            "description": (
                "Redirect to a short-lived presigned storage URL for "
                "the cover image. Browser clients will follow the "
                "redirect transparently; non-browser clients should "
                "either follow redirects or read the `Location` "
                "header without following."
            ),
            "headers": {
                "Location": {
                    "description": ("Presigned URL pointing at the cover object."),
                    "schema": {"type": "string", "format": "uri"},
                },
            },
        },
    },
    error_map={
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
        UserCoverNotFoundError: USER_COVER_NOT_FOUND_RULE,
    },
)
async def get_cover(
    interactor: FromDishka[GetUserCoverQueryHandler],
    user_id: UUID = _USER_ID_PATH,
) -> RedirectResponse:
    """Return the user's cover as a redirect to presigned storage.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected get-cover query handler.

    Returns:
        ``302 Found`` ``RedirectResponse`` to the short-lived presigned
        storage URL for the cover image.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404 via
            ``ENTITY_NOT_FOUND_RULE``.
        UserCoverNotFoundError: The user exists but has no cover
            attached; HTTP 404 via ``USER_COVER_NOT_FOUND_RULE``.
    """
    output = await interactor.run(GetUserCoverQuery(oid=UserID(user_id)))
    return RedirectResponse(
        url=output.url,
        status_code=status.HTTP_302_FOUND,
    )


@router.put(
    "/me/first-name",
    summary="Change the current user's first name",
    operation_id="changeMyFirstName",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_first_name(
    request: Request,
    payload: ChangeFirstNameSchema,
    interactor: FromDishka[ChangeUserFirstNameCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's first name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new first name>"}``; constrained to
            ``FIRST_NAME_MAX_LEN`` chars by the request schema and
            re-validated by the ``FirstName`` value object.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``FirstName`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserFirstNameCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.put(
    "/me/last-name",
    summary="Change the current user's last name",
    operation_id="changeMyLastName",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_last_name(
    request: Request,
    payload: ChangeLastNameSchema,
    interactor: FromDishka[ChangeUserLastNameCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's last name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new last name>"}``; constrained to
            ``LAST_NAME_MAX_LEN`` chars by the request schema and
            re-validated by the ``LastName`` value object.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``LastName`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserLastNameCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.put(
    "/me/patronymic",
    summary="Change or clear the current user's patronymic",
    operation_id="changeMyPatronymic",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_patronymic(
    request: Request,
    payload: ChangePatronymicSchema,
    interactor: FromDishka[ChangeUserPatronymicCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's patronymic (or clear it with ``null``).

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new patronymic>" | null}``; constrained
            to ``PATRONYMIC_MAX_LEN`` chars by the request schema and
            re-validated by the ``Patronymic`` value object.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``Patronymic`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserPatronymicCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.put(
    "/me/description",
    summary="Change or clear the current user's HTML description",
    operation_id="changeMyDescription",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_description(
    request: Request,
    payload: ChangeDescriptionSchema,
    interactor: FromDishka[ChangeUserDescriptionCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace (or clear) the current user's HTML description.

    Incoming HTML is sanitized server-side through the configured
    ``HtmlSanitizer`` — unsafe tags and attributes are stripped before
    the value reaches the domain.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<html>..." | null}``; constrained to
            ``DESCRIPTION_MAX_LEN`` chars **after sanitization**.
            ``null`` clears the description.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: Sanitized description is empty or exceeds the
            length limit; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserDescriptionCommand(user_id=ctx.user_id, html=payload.value)
    )


@router.post(
    "/me/avatar",
    summary="Upload (or replace) the current user's avatar",
    operation_id="uploadMyAvatar",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=FileSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def upload_avatar(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetUserAvatarCommandHandler],
    auth: FromDishka[Authenticator],
) -> FileSchema:
    """Upload (or replace) the current user's avatar.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` carrying the image
            bytes. Capped at ``MAX_FILE_SIZE_BYTES``
            (``5 MB``); the server reads `Content-Type` from the
            upload and rejects payloads above the limit with a 422
            ``FileTooLargeError``.
        interactor: Injected set-avatar command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FileTooLargeError: Payload over ``MAX_FILE_SIZE_BYTES``; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_image_upload(file)
    file_id = await interactor.run(
        SetUserAvatarCommand(
            user_id=ctx.user_id,
            data=data,
            content_type=content_type,
        )
    )
    return FileSchema(oid=file_id)


@router.delete(
    "/me/avatar",
    summary="Detach the current user's avatar",
    operation_id="deleteMyAvatar",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def delete_avatar(
    request: Request,
    interactor: FromDishka[RemoveUserAvatarCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Detach the current user's avatar.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-avatar command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(RemoveUserAvatarCommand(user_id=ctx.user_id))


@router.post(
    "/me/cover",
    summary="Upload (or replace) the current user's cover",
    operation_id="uploadMyCover",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=FileSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def upload_cover(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetUserCoverCommandHandler],
    auth: FromDishka[Authenticator],
) -> FileSchema:
    """Upload (or replace) the current user's cover.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` carrying the image
            bytes. Capped at ``MAX_FILE_SIZE_BYTES``
            (``5 MB``); the server reads `Content-Type` from the
            upload and rejects payloads above the limit with a 422
            ``FileTooLargeError``.
        interactor: Injected set-cover command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FileTooLargeError: Payload over ``MAX_FILE_SIZE_BYTES``; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_image_upload(file)
    file_id = await interactor.run(
        SetUserCoverCommand(
            user_id=ctx.user_id,
            data=data,
            content_type=content_type,
        )
    )
    return FileSchema(oid=file_id)


@router.delete(
    "/me/cover",
    summary="Detach the current user's cover",
    operation_id="deleteMyCover",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def delete_cover(
    request: Request,
    interactor: FromDishka[RemoveUserCoverCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Detach the current user's cover.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-cover command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(RemoveUserCoverCommand(user_id=ctx.user_id))


@router.put(
    "/me/website-url",
    summary="Change or clear the current user's personal website URL",
    operation_id="changeMyWebsiteUrl",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_website_url(
    request: Request,
    payload: ChangeWebsiteUrlSchema,
    interactor: FromDishka[ChangeUserWebsiteUrlCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace (or clear) the current user's personal website URL.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "https://..." | null}``; constrained to
            ``WEBSITE_URL_MAX_LEN`` chars by the request schema and
            re-validated by the ``WebsiteUrl`` value object.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``WebsiteUrl`` VO invariants violated (empty,
            too long, or non-`http(s)` scheme); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserWebsiteUrlCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.put(
    "/me/portfolio-url",
    summary="Change or clear the current user's portfolio URL",
    operation_id="changeMyPortfolioUrl",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_portfolio_url(
    request: Request,
    payload: ChangePortfolioUrlSchema,
    interactor: FromDishka[ChangeUserPortfolioUrlCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace (or clear) the current user's portfolio URL.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "https://..." | null}``.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``PortfolioUrl`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserPortfolioUrlCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.put(
    "/me/public-email",
    summary="Change or clear the current user's public contact email",
    operation_id="changeMyPublicEmail",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_public_email(
    request: Request,
    payload: ChangePublicEmailSchema,
    interactor: FromDishka[ChangeUserPublicEmailCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace (or clear) the public contact email shown on the profile.

    Distinct from the login email — there is no verification step;
    the user is solely responsible for the address they publish.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "contact@example.com" | null}``.
        interactor: Injected command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: ``PublicEmail`` VO invariants violated (no `@`
            or value too long); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeUserPublicEmailCommand(user_id=ctx.user_id, value=payload.value)
    )


@router.get(
    "/{user_id}/products",
    summary="List the user's published products",
    operation_id="getUserProducts",
    response_model=list[ProductSchema],
)
async def get_products(
    interactor: FromDishka[GetUserProductsQueryHandler],
    user_id: UUID = _USER_ID_PATH,
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset (rows to skip), `>= 0`.",
        examples=[0],
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`)."),
        examples=[20],
    ),
) -> list[ProductSchema]:
    """Return ``user_id``'s published products, newest first.

    Powers the public profile page's "products" rail. Drafts,
    archived, and banned products are excluded — only ``PUBLISHED``
    rows are visible. An unknown ``user_id`` simply returns an empty
    list rather than 404 so the rail renders an empty state without
    breaking the rest of the profile page.

    Args:
        interactor: Injected list-user-products query handler.
        user_id: Target user's UUID, parsed from the URL path.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        List of :class:`ProductSchema`, ordered by ``created_at``
        descending. Empty when the user has no published products
        (or does not exist).
    """
    views = await interactor.run(
        GetUserProductsQuery(
            user_id=UserID(user_id),
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [ProductSchema.from_output(view) for view in views]
