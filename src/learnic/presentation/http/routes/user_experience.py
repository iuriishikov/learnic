from datetime import date
from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, UploadFile, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from learnic.application.commands.user_experience.add import (
    AddUserExperienceCommand,
    AddUserExperienceCommandHandler,
)
from learnic.application.commands.user_experience.delete import (
    DeleteUserExperienceCommand,
    DeleteUserExperienceCommandHandler,
)
from learnic.application.commands.user_experience.icon.remove import (
    RemoveUserExperienceIconCommand,
    RemoveUserExperienceIconCommandHandler,
)
from learnic.application.commands.user_experience.icon.set import (
    SetUserExperienceIconCommand,
    SetUserExperienceIconCommandHandler,
)
from learnic.application.commands.user_experience.update import (
    UpdateUserExperienceCommand,
    UpdateUserExperienceCommandHandler,
)
from learnic.application.queries.user_experience.list_for_user import (
    ListUserExperiencesQuery,
    ListUserExperiencesQueryHandler,
    UserExperienceOutput,
)
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.constants import (
    DESCRIPTION_MAX_LEN,
    SOURCE_URL_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.entities.common.limits import ResourceLimitReachedError
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    RESOURCE_LIMIT_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import (
    FileSchema,
    UploadedFileSchema,
)
from learnic.presentation.http.common.upload_limits import (
    USER_EXPERIENCE_ICON_MAX_BYTES,
)
from learnic.presentation.http.common.uploads import read_upload

router = ErrorAwareRouter(
    prefix="/users/{user_id}/experiences",
    tags=["UserExperiences"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/experiences",
    tags=["UserExperiences"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]

_USER_ID_PATH: Final = Path(
    description="Target user's UUID.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)
_EXPERIENCE_ID_PATH: Final = Path(
    description="Target experience entry's UUID.",
    examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
)


class AddUserExperienceSchema(BaseModel):
    """Body for `POST /users/me/experiences`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Product Designer at Spherule",
                    "description": "Lead the redesign of the editor flow.",
                    "start_date": "2018-01-01",
                    "end_date": "2020-05-01",
                    "source_url": "https://spherule.example.com/projects/editor",
                },
            ],
        },
    )

    title: str = Field(
        description=(
            "Headline for the entry — typically the role or program name. "
            f"Required, non-empty after trimming. Max length is "
            f"{TITLE_MAX_LEN} characters (`TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
        examples=["Product Designer at Spherule"],
    )
    description: str | None = Field(
        default=None,
        description=(
            "Optional free-text description. `null` to leave it empty. "
            f"Max length is {DESCRIPTION_MAX_LEN} characters "
            "(`DESCRIPTION_MAX_LEN`)."
        ),
        max_length=DESCRIPTION_MAX_LEN,
        examples=["Lead the redesign of the editor flow.", None],
    )
    start_date: date = Field(
        description="Day the experience started (ISO 8601 calendar date).",
        examples=["2018-01-01"],
    )
    end_date: date | None = Field(
        default=None,
        description=(
            "Day the experience ended, or `null` for ongoing entries "
            "(`Jan 2018 – Present`). Must not precede `start_date`."
        ),
        examples=["2020-05-01", None],
    )
    source_url: str | None = Field(
        default=None,
        description=(
            "Optional external link (must start with `http://` or "
            f"`https://`). Max length is {SOURCE_URL_MAX_LEN} characters "
            "(`SOURCE_URL_MAX_LEN`)."
        ),
        max_length=SOURCE_URL_MAX_LEN,
        examples=[
            "https://spherule.example.com/projects/editor",
            None,
        ],
    )


class UpdateUserExperienceSchema(BaseModel):
    """Body for `PUT /users/me/experiences/{experience_id}`.

    Replaces every editable field. Send `null` for ``description``,
    ``end_date`` or ``source_url`` to clear those fields. The icon
    is managed separately via the icon endpoints, so it is not part
    of this payload.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Senior Product Designer at Spherule",
                    "description": None,
                    "start_date": "2018-01-01",
                    "end_date": None,
                    "source_url": None,
                },
            ],
        },
    )

    title: str = Field(
        description=(
            "Headline for the entry — typically the role or program name. "
            f"Required, non-empty after trimming. Max length is "
            f"{TITLE_MAX_LEN} characters (`TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
        examples=["Senior Product Designer at Spherule"],
    )
    description: str | None = Field(
        description=(
            "Optional free-text description. `null` to clear the field. "
            f"Max length is {DESCRIPTION_MAX_LEN} characters "
            "(`DESCRIPTION_MAX_LEN`)."
        ),
        max_length=DESCRIPTION_MAX_LEN,
        examples=["Lead the redesign of the editor flow.", None],
    )
    start_date: date = Field(
        description="Day the experience started (ISO 8601 calendar date).",
        examples=["2018-01-01"],
    )
    end_date: date | None = Field(
        description=(
            "Day the experience ended, or `null` for ongoing entries. "
            "Must not precede `start_date`."
        ),
        examples=["2020-05-01", None],
    )
    source_url: str | None = Field(
        description=(
            "Optional external link (must start with `http://` or "
            f"`https://`). `null` clears it. Max length is "
            f"{SOURCE_URL_MAX_LEN} characters (`SOURCE_URL_MAX_LEN`)."
        ),
        max_length=SOURCE_URL_MAX_LEN,
        examples=[
            "https://spherule.example.com/projects/editor",
            None,
        ],
    )


class UserExperienceSchema(BaseModel):
    """A single experience entry on a user's profile.

    Returned in the catalogue order (most recent ``start_date``
    first) by `GET /users/{user_id}/experiences`.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "oid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "Product Designer at Spherule",
                    "description": "Lead the redesign of the editor flow.",
                    "start_date": "2018-01-01",
                    "end_date": "2020-05-01",
                    "source_url": ("https://spherule.example.com/projects/editor"),
                    "icon": {
                        "oid": "11111111-2222-3333-4444-555555555555",
                        "content_type": "image/png",
                        "size_bytes": 32_768,
                        "url": "https://s3.example.com/icons/exp.png",
                    },
                },
            ],
        },
    )

    oid: UUID = Field(
        description="Experience entry's stable identifier (UUID v4).",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )
    user_id: UUID = Field(
        description="Owning user's UUID.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    title: str = Field(
        description=(
            "Headline for the entry. "
            f"Max length is {TITLE_MAX_LEN} characters "
            "(`TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
        examples=["Product Designer at Spherule"],
    )
    description: str | None = Field(
        description=(
            "Optional free-text description, or `null` when not set. "
            f"Max length is {DESCRIPTION_MAX_LEN} characters "
            "(`DESCRIPTION_MAX_LEN`)."
        ),
        max_length=DESCRIPTION_MAX_LEN,
        examples=["Lead the redesign of the editor flow.", None],
    )
    start_date: date = Field(
        description="Day the experience started (ISO 8601 calendar date).",
        examples=["2018-01-01"],
    )
    end_date: date | None = Field(
        description=("Day the experience ended, or `null` for ongoing entries."),
        examples=["2020-05-01", None],
    )
    source_url: str | None = Field(
        description=(
            "Optional external link, or `null` when not set. "
            f"Max length is {SOURCE_URL_MAX_LEN} characters "
            "(`SOURCE_URL_MAX_LEN`)."
        ),
        max_length=SOURCE_URL_MAX_LEN,
        examples=[
            "https://spherule.example.com/projects/editor",
            None,
        ],
    )
    icon: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved icon file with a short-lived presigned URL, or "
            "`null` when no icon is attached. The URL expires; "
            "re-fetch the list to get a fresh one."
        ),
    )

    @classmethod
    def from_view(cls, view: UserExperienceOutput) -> Self:
        return cls.model_validate(view)


class CreatedUserExperienceSchema(BaseModel):
    """201 response body for `POST /users/me/experiences`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"oid": "7c9e6679-7425-40de-944b-e07fc1f90ae7"}],
        },
    )

    oid: UUID = Field(
        description="Identifier of the newly-created experience.",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )


@router.get(
    "",
    summary="List a user's work / study experience entries",
    operation_id="listUserExperiences",
    response_model=list[UserExperienceSchema],
)
async def list_for_user(
    interactor: FromDishka[ListUserExperiencesQueryHandler],
    user_id: UUID = _USER_ID_PATH,
) -> list[UserExperienceSchema]:
    """Return every experience entry attached to the user.

    Sorted by ``start_date`` descending (most recent first) with
    ``oid`` as a secondary tiebreaker. Public — no authentication
    required — so SPAs can render the timeline on the public
    profile page.

    Args:
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected list-experiences query handler.

    Returns:
        List of :class:`UserExperienceSchema`, possibly empty.
    """
    views = await interactor.run(
        ListUserExperiencesQuery(user_id=UserID(user_id)),
    )
    return [UserExperienceSchema.from_view(view) for view in views]


@me_router.post(
    "",
    summary="Add a new experience entry for the current user",
    operation_id="addMyUserExperience",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedUserExperienceSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {ResourceLimitReachedError: RESOURCE_LIMIT_RULE},
)
async def add(
    request: Request,
    payload: AddUserExperienceSchema,
    interactor: FromDishka[AddUserExperienceCommandHandler],
    auth: FromDishka[Authenticator],
) -> CreatedUserExperienceSchema:
    """Create a new experience entry for the authenticated user.

    The icon is uploaded separately through
    `POST /users/me/experiences/{experience_id}/icon` — keeps the
    create payload JSON-only.

    Args:
        request: Source of the access-token cookie.
        payload: Title / description / dates / source URL of the
            new entry. Length limits come from
            `entities/user_experience/constants.py`.
        interactor: Injected add-experience command handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``201 Created`` with :class:`CreatedUserExperienceSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Authenticated user vanished; HTTP 404.
        FieldError: A VO invariant was violated (empty title, bad
            date range, bad URL scheme, value too long); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    experience_id = await interactor.run(
        AddUserExperienceCommand(
            user_id=ctx.user_id,
            title=payload.title,
            start_date=payload.start_date,
            end_date=payload.end_date,
            description=payload.description,
            source_url=payload.source_url,
        ),
    )
    return CreatedUserExperienceSchema(oid=experience_id)


@me_router.put(
    "/{experience_id}",
    summary="Replace an experience entry of the current user",
    operation_id="updateMyUserExperience",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update(
    request: Request,
    payload: UpdateUserExperienceSchema,
    interactor: FromDishka[UpdateUserExperienceCommandHandler],
    auth: FromDishka[Authenticator],
    experience_id: UUID = _EXPERIENCE_ID_PATH,
) -> None:
    """Replace every editable field of an existing experience entry.

    The icon is managed through its own endpoint pair and is left
    untouched by this call.

    Args:
        request: Source of the access-token cookie.
        payload: Replacement values for every editable field.
        interactor: Injected update command handler.
        auth: Injected authenticator that validates the access cookie.
        experience_id: Target entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller does not own the entry; HTTP 403.
        EntityNotFoundError: No entry with the given id; HTTP 404.
        FieldError: A VO invariant was violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateUserExperienceCommand(
            actor_id=ctx.user_id,
            experience_id=UserExperienceID(experience_id),
            title=payload.title,
            start_date=payload.start_date,
            end_date=payload.end_date,
            description=payload.description,
            source_url=payload.source_url,
        ),
    )


@me_router.delete(
    "/{experience_id}",
    summary="Delete an experience entry of the current user",
    operation_id="deleteMyUserExperience",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_experience(
    request: Request,
    interactor: FromDishka[DeleteUserExperienceCommandHandler],
    auth: FromDishka[Authenticator],
    experience_id: UUID = _EXPERIENCE_ID_PATH,
) -> None:
    """Delete an experience entry (and soft-delete its icon file, if any).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected delete command handler.
        auth: Injected authenticator that validates the access cookie.
        experience_id: Target entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller does not own the entry; HTTP 403.
        EntityNotFoundError: No entry with the given id; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteUserExperienceCommand(
            actor_id=ctx.user_id,
            experience_id=UserExperienceID(experience_id),
        ),
    )


@me_router.post(
    "/{experience_id}/icon",
    summary="Upload (or replace) the icon for an experience entry",
    operation_id="uploadMyUserExperienceIcon",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=UploadedFileSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def upload_icon(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetUserExperienceIconCommandHandler],
    auth: FromDishka[Authenticator],
    experience_id: UUID = _EXPERIENCE_ID_PATH,
) -> UploadedFileSchema:
    """Upload (or replace) the icon image attached to an experience.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` carrying the
            image bytes. Capped at ``USER_EXPERIENCE_ICON_MAX_BYTES``;
            the server rejects payloads above the limit with HTTP 422
            ``FileTooLarge``.
        interactor: Injected set-icon command handler.
        auth: Injected authenticator that validates the access cookie.
        experience_id: Target entry's UUID, parsed from the URL path.

    Returns:
        :class:`UploadedFileSchema` with the new file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller does not own the entry; HTTP 403.
        EntityNotFoundError: No entry with the given id; HTTP 404.
        FileTooLargeError: Payload exceeds the upload cap; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_upload(
        file, max_bytes=USER_EXPERIENCE_ICON_MAX_BYTES,
    )
    file_id = await interactor.run(
        SetUserExperienceIconCommand(
            actor_id=ctx.user_id,
            experience_id=UserExperienceID(experience_id),
            data=data,
            content_type=content_type,
        ),
    )
    return UploadedFileSchema(oid=file_id)


@me_router.delete(
    "/{experience_id}/icon",
    summary="Detach the icon from an experience entry",
    operation_id="deleteMyUserExperienceIcon",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_icon(
    request: Request,
    interactor: FromDishka[RemoveUserExperienceIconCommandHandler],
    auth: FromDishka[Authenticator],
    experience_id: UUID = _EXPERIENCE_ID_PATH,
) -> None:
    """Detach the icon and soft-delete the underlying file row.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-icon command handler.
        auth: Injected authenticator that validates the access cookie.
        experience_id: Target entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller does not own the entry; HTTP 403.
        EntityNotFoundError: No entry with the given id; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RemoveUserExperienceIconCommand(
            actor_id=ctx.user_id,
            experience_id=UserExperienceID(experience_id),
        ),
    )
