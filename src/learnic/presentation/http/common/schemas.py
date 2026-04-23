"""Schemas shared between multiple routers at the HTTP boundary."""

from uuid import UUID

from pydantic import BaseModel
from typing_extensions import Self

from learnic.application.queries.user.get import UserOutput
from learnic.application.queries.user.get_avatar import UserAvatarOutput
from learnic.application.queries.user.get_cover import UserCoverOutput


class FileSchema(BaseModel):
    """Reference to a file resource.

    Returned whenever an endpoint produces or owns a file — avatar and
    cover uploads today, course banners, message attachments, etc. in
    the future. Start with just the identifier; grow with extra fields
    (URL, MIME, size) as concrete endpoints need them.
    """

    oid: UUID


class UserSchema(BaseModel):
    """Public user profile. ``email`` is intentionally not exposed."""

    oid: UUID
    first_name: str
    last_name: str
    patronymic: str | None
    description: str | None
    avatar_url: str | None
    cover_url: str | None

    @classmethod
    def from_view(cls, view: UserOutput) -> Self:
        """Build the schema from a ``GetUserQueryHandler`` output."""
        return cls(
            oid=view.oid,
            first_name=view.first_name,
            last_name=view.last_name,
            patronymic=view.patronymic,
            description=view.description,
            avatar_url=view.avatar_url,
            cover_url=view.cover_url,
        )


class UserAvatarSchema(BaseModel):
    """Avatar link for a user.

    ``avatar`` is ``null`` when the user has no avatar attached. The
    ``/users/{user_id}/avatar`` endpoint returns this shape only on the
    ``null`` path; when the avatar exists, the endpoint redirects to the
    presigned storage URL instead.
    """

    avatar: str | None

    @classmethod
    def from_view(cls, view: UserAvatarOutput) -> Self:
        """Build the schema from a ``GetUserAvatarQueryHandler`` output."""
        return cls(avatar=view.url)


class UserCoverSchema(BaseModel):
    """Cover link for a user.

    ``cover`` is ``null`` when the user has no cover attached. The
    ``/users/{user_id}/cover`` endpoint returns this shape only on the
    ``null`` path; when the cover exists, the endpoint redirects to the
    presigned storage URL instead.
    """

    cover: str | None

    @classmethod
    def from_view(cls, view: UserCoverOutput) -> Self:
        """Build the schema from a ``GetUserCoverQueryHandler`` output."""
        return cls(cover=view.url)


class StringFieldSchema(BaseModel):
    """Payload for endpoints that replace a single required string field."""

    value: str


class NullableStringFieldSchema(BaseModel):
    """Payload for endpoints that replace a single optional field.

    ``value = null`` clears the field.
    """

    value: str | None
