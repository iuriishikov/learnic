from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.formatting import (
    build_full_name,
    mask_email,
)
from learnic.application.common.persistence.user import UserReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.validators import validate_empty
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserQuery:
    oid: UserID


@dataclass(slots=True, frozen=True)
class UserOutput:
    """Query result with media URLs already resolved.

    ``full_name`` collapses ``last_name`` / ``first_name`` /
    ``patronymic`` into the canonical Russian-style display name.
    ``email`` is masked via :func:`mask_email` so the public profile
    projection never leaks a plain address. ``public_email`` is the
    optional, user-supplied contact email distinct from the login
    address — surfaced un-masked because the user explicitly
    chose to publish it.
    """

    oid: UserID
    full_name: str
    email: str
    is_verified: bool
    description: str | None
    avatar_url: str | None
    cover_url: str | None
    website_url: str | None
    portfolio_url: str | None
    public_email: str | None


@final
class GetUserQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetUserQuery) -> UserOutput:
        view = validate_empty(await self._reader.with_id(data.oid), data.oid)

        avatar_url: str | None = None
        if view.avatar is not None:
            avatar_url = await self._file_storage.presigned_get_url(
                view.avatar.bucket, view.avatar.storage_name
            )

        cover_url: str | None = None
        if view.cover is not None:
            cover_url = await self._file_storage.presigned_get_url(
                view.cover.bucket, view.cover.storage_name
            )

        return UserOutput(
            oid=view.oid,
            full_name=build_full_name(view.first_name, view.last_name, view.patronymic),
            email=mask_email(view.email),
            is_verified=view.is_verified,
            description=view.description,
            avatar_url=avatar_url,
            cover_url=cover_url,
            website_url=view.website_url,
            portfolio_url=view.portfolio_url,
            public_email=view.public_email,
        )
