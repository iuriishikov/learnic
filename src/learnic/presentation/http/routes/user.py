from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi_error_map import ErrorAwareRouter

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
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommand,
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommand,
    SetUserCoverCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
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
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import Authenticator
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import (
    FileSchema,
    NullableStringFieldSchema,
    StringFieldSchema,
    UserAvatarSchema,
    UserCoverSchema,
    UserSchema,
)
from learnic.presentation.http.common.uploads import read_image_upload

router = ErrorAwareRouter(
    prefix="/users",
    tags=["Users"],
    route_class=DishkaErrorAwareRoute,
)


@router.get(
    "/{user_id}",
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get(
    user_id: UUID,
    interactor: FromDishka[GetUserQueryHandler],
) -> UserSchema:
    """Return a user by id with presigned URLs for avatar/cover.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected get-user query handler.

    Returns:
        ``UserSchema`` with profile fields and short-lived presigned
        URLs for avatar/cover (``null`` if not set). ``email`` is
        deliberately omitted.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    view = await interactor.run(GetUserQuery(oid=UserID(user_id)))
    return UserSchema.from_view(view)


@router.get(
    "/{user_id}/avatar",
    response_model=UserAvatarSchema,
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to the presigned storage URL.",
        },
    },
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_avatar(
    user_id: UUID,
    interactor: FromDishka[GetUserAvatarQueryHandler],
) -> UserAvatarSchema | RedirectResponse:
    """Return the user's avatar as a redirect to presigned storage.

    When the user has no avatar attached, responds with JSON
    ``{"avatar": null}`` so clients can branch without following a
    redirect; otherwise issues a short-lived 302 to the presigned
    storage URL.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected get-avatar query handler.

    Returns:
        :class:`UserAvatarSchema` with ``avatar = null`` when the user
        has no avatar, or a 302 ``RedirectResponse`` to the presigned
        storage URL when an avatar is attached.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    output = await interactor.run(
        GetUserAvatarQuery(oid=UserID(user_id))
    )
    if output.url is None:
        return UserAvatarSchema.from_view(output)
    return RedirectResponse(
        url=output.url,
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/{user_id}/cover",
    response_model=UserCoverSchema,
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to the presigned storage URL.",
        },
    },
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_cover(
    user_id: UUID,
    interactor: FromDishka[GetUserCoverQueryHandler],
) -> UserCoverSchema | RedirectResponse:
    """Return the user's cover as a redirect to presigned storage.

    When the user has no cover attached, responds with JSON
    ``{"cover": null}`` so clients can branch without following a
    redirect; otherwise issues a short-lived 302 to the presigned
    storage URL.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected get-cover query handler.

    Returns:
        :class:`UserCoverSchema` with ``cover = null`` when the user
        has no cover, or a 302 ``RedirectResponse`` to the presigned
        storage URL when a cover is attached.

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    output = await interactor.run(
        GetUserCoverQuery(oid=UserID(user_id))
    )
    if output.url is None:
        return UserCoverSchema.from_view(output)
    return RedirectResponse(
        url=output.url,
        status_code=status.HTTP_302_FOUND,
    )


@router.put(
    "/me/first-name",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_first_name(
    request: Request,
    payload: StringFieldSchema,
    interactor: FromDishka[ChangeUserFirstNameCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's first name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new first name>"}``.
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
    status_code=status.HTTP_204_NO_CONTENT,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_last_name(
    request: Request,
    payload: StringFieldSchema,
    interactor: FromDishka[ChangeUserLastNameCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's last name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new last name>"}``.
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
    status_code=status.HTTP_204_NO_CONTENT,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_patronymic(
    request: Request,
    payload: NullableStringFieldSchema,
    interactor: FromDishka[ChangeUserPatronymicCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace the current user's patronymic (or clear it with ``null``).

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new patronymic>" | null}``.
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
    status_code=status.HTTP_204_NO_CONTENT,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def change_description(
    request: Request,
    payload: NullableStringFieldSchema,
    interactor: FromDishka[ChangeUserDescriptionCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Replace (or clear) the current user's HTML description.

    Incoming HTML is sanitized server-side through the configured
    ``HtmlSanitizer`` — unsafe tags and attributes are stripped before
    the value reaches the domain.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<html>..." | null}``. ``null`` clears it.
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
    status_code=status.HTTP_201_CREATED,
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
        file: ``multipart/form-data`` field ``file`` with any payload
            up to 5 MB.
        interactor: Injected set-avatar command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FileTooLargeError: Payload over 5 MB; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_image_upload(file)
    file_id = await interactor.run(
        SetUserAvatarCommand(user_id=ctx.user_id, data=data, content_type=content_type)
    )
    return FileSchema(oid=file_id)


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
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
    status_code=status.HTTP_201_CREATED,
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
        file: ``multipart/form-data`` field ``file`` with any payload
            up to 5 MB.
        interactor: Injected set-cover command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FileTooLargeError: Payload over 5 MB; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_image_upload(file)
    file_id = await interactor.run(
        SetUserCoverCommand(user_id=ctx.user_id, data=data, content_type=content_type)
    )
    return FileSchema(oid=file_id)


@router.delete(
    "/me/cover",
    status_code=status.HTTP_204_NO_CONTENT,
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
