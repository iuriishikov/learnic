from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, UploadFile, status
from pydantic import BaseModel

from learnic.application.commands.user.avatar.remove import (
    RemoveUserAvatarCommand,
    RemoveUserAvatarCommandHandler,
)
from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommand,
    SetUserAvatarCommandHandler,
)
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommand,
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommand,
    SetUserCoverCommandHandler,
)
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.application.queries.user.get import (
    GetUserQuery,
    GetUserQueryHandler,
)
from learnic.entities.file.constants import MAX_FILE_SIZE_BYTES
from learnic.entities.file.errors import FileTooLargeError
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import authenticate
from learnic.presentation.http.common.schemas import FileSchema

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=DishkaRoute,
)


class UserSchema(BaseModel):
    oid: UUID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None
    avatar_url: str | None
    cover_url: str | None


async def _read_image_upload(file: UploadFile) -> tuple[bytes, str]:
    """Read the body and return ``(bytes, content_type)``.

    Aborts early if the body is bigger than the VO limit — avoids
    buffering arbitrary user uploads into memory.
    """
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    # Enforce size ceiling at the HTTP layer; the ``FileSize`` VO
    # re-checks inside the handler.
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(MAX_FILE_SIZE_BYTES)
    content_type = file.content_type or "application/octet-stream"
    return data, content_type


@router.get("/{user_id}")
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
        URLs for avatar/cover (``null`` if not set).

    Raises:
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    view = await interactor.run(GetUserQuery(oid=UserID(user_id)))
    return UserSchema(
        oid=view.oid,
        email=view.email,
        first_name=view.first_name,
        last_name=view.last_name,
        patronymic=view.patronymic,
        avatar_url=view.avatar_url,
        cover_url=view.cover_url,
    )


@router.post(
    "/me/avatar",
    status_code=status.HTTP_201_CREATED,
    response_model=FileSchema,
)
async def upload_avatar(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetUserAvatarCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
) -> FileSchema:
    """Upload (or replace) the current user's avatar.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` with any payload
            up to 5 MB.
        interactor: Injected set-avatar command handler.
        access_tokens: Injected access-token service.
        denylist: Injected access-token denylist.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        FileTooLargeError: Payload over 5 MB; HTTP 422.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    data, content_type = await _read_image_upload(file)
    file_id = await interactor.run(
        SetUserAvatarCommand(user_id=ctx.user_id, data=data, content_type=content_type)
    )
    return FileSchema(oid=file_id)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    request: Request,
    interactor: FromDishka[RemoveUserAvatarCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
) -> None:
    """Detach the current user's avatar.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-avatar command handler.
        access_tokens: Injected access-token service.
        denylist: Injected access-token denylist.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    await interactor.run(RemoveUserAvatarCommand(user_id=ctx.user_id))


@router.post(
    "/me/cover",
    status_code=status.HTTP_201_CREATED,
    response_model=FileSchema,
)
async def upload_cover(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetUserCoverCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
) -> FileSchema:
    """Upload (or replace) the current user's cover.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` with any payload
            up to 5 MB.
        interactor: Injected set-cover command handler.
        access_tokens: Injected access-token service.
        denylist: Injected access-token denylist.

    Returns:
        :class:`FileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        FileTooLargeError: Payload over 5 MB; HTTP 422.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    data, content_type = await _read_image_upload(file)
    file_id = await interactor.run(
        SetUserCoverCommand(user_id=ctx.user_id, data=data, content_type=content_type)
    )
    return FileSchema(oid=file_id)


@router.delete("/me/cover", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover(
    request: Request,
    interactor: FromDishka[RemoveUserCoverCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
) -> None:
    """Detach the current user's cover.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-cover command handler.
        access_tokens: Injected access-token service.
        denylist: Injected access-token denylist.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    await interactor.run(RemoveUserCoverCommand(user_id=ctx.user_id))
