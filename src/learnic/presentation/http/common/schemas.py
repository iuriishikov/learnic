"""Schemas shared between multiple routers at the HTTP boundary.

Every field carries an OpenAPI-visible ``description`` and at least one
``example``. Length limits mirror the ``constants.py`` of the matching
aggregate so the generated client validates the same invariants the
domain enforces.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from learnic.application.common.formatting import build_full_name, mask_email
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.application.queries.user.get import UserOutput
from learnic.application.queries.user.search import UserSummaryOutput
from learnic.entities.user.constants import (
    DESCRIPTION_MAX_LEN,
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PATRONYMIC_MAX_LEN,
)

_FULL_NAME_MAX_LEN: int = (
    FIRST_NAME_MAX_LEN + LAST_NAME_MAX_LEN + PATRONYMIC_MAX_LEN + 2
)
"""Upper bound on a joined ``Last First Patronymic`` string.

Two extra characters cover the spaces between the parts. The same
value caps :class:`UserSchema.full_name` and :class:`UserSummarySchema.full_name`.
"""

_MASKED_EMAIL_DESCRIPTION = (
    "Privacy-respecting masked address in the form "
    "`f*****d@domain.com` — the first and last characters of the "
    "local part are preserved, everything in between collapses to a "
    "fixed asterisk run, and the domain stays intact. Use it for "
    "display only; never echo it back as login input."
)


class FileSchema(BaseModel):
    """Reference to a file resource owned by the API.

    Returned whenever an endpoint produces or owns a file — avatar and
    cover uploads today; course banners, message attachments, etc. in
    the future. Start with just the identifier; grow with extra fields
    (URL, MIME, size) as concrete endpoints need them.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "550e8400-e29b-41d4-a716-446655440000"},
            ],
        },
    )

    oid: UUID = Field(
        description=(
            "Server-generated UUID identifying the stored file. Use it "
            "to fetch presigned download URLs from the appropriate "
            "aggregate endpoint (e.g. `GET /users/{user_id}/avatar`)."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class UserSchema(BaseModel):
    """Public user profile.

    The user's identity is exposed as a single ``full_name`` string
    (``Last First Patronymic``) plus a ``email`` masked through the
    canonical ``f*****d@domain.com`` form so the API never returns a
    plain address.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "full_name": "Lovelace Ada",
                    "email": "a*****a@example.com",
                    "description": "<p>Mathematician.</p>",
                    "avatar_url": "https://s3.example.com/avatars/...",
                    "cover_url": None,
                },
            ],
        },
    )

    oid: UUID = Field(
        description="User's stable identifier (UUID v4).",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    full_name: str = Field(
        description=(
            "Display name in the canonical Russian-style "
            "`Last First Patronymic` order. Whitespace-trimmed; "
            "missing patronymic collapses to `Last First`."
        ),
        min_length=1,
        max_length=_FULL_NAME_MAX_LEN,
        examples=["Lovelace Ada"],
    )
    email: str = Field(
        description=_MASKED_EMAIL_DESCRIPTION,
        min_length=1,
        max_length=EMAIL_MAX_LEN,
        examples=["a*****a@example.com"],
    )
    description: str | None = Field(
        description=(
            "User-authored profile description as sanitized HTML. "
            "`null` when the user has not set one. The server "
            "sanitizes the markup before storage; clients can render "
            "the value directly."
        ),
        max_length=DESCRIPTION_MAX_LEN,
        examples=[None, "<p>Hello world.</p>"],
    )
    avatar_url: str | None = Field(
        description=(
            "Short-lived presigned URL for the user's avatar, or "
            "`null` when no avatar is attached. The URL expires; "
            "re-fetch the user resource to get a fresh one."
        ),
        examples=[
            None,
            "https://s3.example.com/avatars/user.png?X-Amz-Signature=...",
        ],
    )
    cover_url: str | None = Field(
        description=(
            "Short-lived presigned URL for the user's cover image, or "
            "`null` when no cover is attached. The URL expires; "
            "re-fetch the user resource to get a fresh one."
        ),
        examples=[
            None,
            "https://s3.example.com/covers/user.png?X-Amz-Signature=...",
        ],
    )

    @classmethod
    def from_view(cls, view: UserOutput) -> Self:
        """Build the schema from a ``GetUserQueryHandler`` output."""
        return cls(
            oid=view.oid,
            full_name=view.full_name,
            email=view.email,
            description=view.description,
            avatar_url=view.avatar_url,
            cover_url=view.cover_url,
        )


class UserSummarySchema(BaseModel):
    """Lightweight user projection returned by name search.

    Like :class:`UserSchema` it omits ``description`` — the search
    endpoint is general-purpose, so private fields stay private.
    ``cover_url`` is also omitted because callers display a single
    thumbnail per hit, not a full profile card. ``email`` is **not**
    surfaced at all here, even masked, because the search endpoint
    must not let an attacker enumerate registered addresses.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "full_name": "Lovelace Ada",
                    "avatar_url": "https://s3.example.com/avatars/...",
                },
            ],
        },
    )

    oid: UUID = Field(
        description="User's stable identifier (UUID v4).",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    full_name: str = Field(
        description=(
            "Display name in the canonical Russian-style "
            "`Last First Patronymic` order. Whitespace-trimmed; "
            "missing patronymic collapses to `Last First`."
        ),
        min_length=1,
        max_length=_FULL_NAME_MAX_LEN,
        examples=["Lovelace Ada"],
    )
    avatar_url: str | None = Field(
        description=(
            "Short-lived presigned URL for the user's avatar, or "
            "`null` when no avatar is attached. The URL expires; "
            "re-issue the search to get a fresh one."
        ),
        examples=[
            None,
            "https://s3.example.com/avatars/user.png?X-Amz-Signature=...",
        ],
    )

    @classmethod
    def from_view(cls, view: UserSummaryOutput) -> Self:
        """Build the schema from a ``SearchUsersQueryHandler`` hit."""
        return cls(
            oid=view.oid,
            full_name=view.full_name,
            avatar_url=view.avatar_url,
        )


class UserRefSchema(BaseModel):
    """Unified user reference embedded in parent resources.

    Returned wherever the API exposes a user *as a reference inside
    another resource* — product author, collaboration collaborator,
    notification actor, and so on. Carries the user's identifier, the
    canonical ``Last First Patronymic`` display name, and a
    privacy-masked email so the SPA can render the row without a
    follow-up ``GET /users/{id}``.

    Distinct from :class:`UserSchema`, which is the full profile
    projection (``GET /users/{id}``) and adds avatar, cover, and
    description on top of these fields. Distinct from
    :class:`UserSummarySchema`, which intentionally omits ``email``
    to keep the public name-search endpoint immune to address
    enumeration.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "full_name": "Lovelace Ada",
                    "email": "a*****a@example.com",
                },
            ],
        },
    )

    oid: UUID = Field(
        description="User's stable identifier (UUID v4).",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    full_name: str = Field(
        description=(
            "Display name in the canonical Russian-style "
            "`Last First Patronymic` order. Whitespace-trimmed; "
            "missing patronymic collapses to `Last First`."
        ),
        min_length=1,
        max_length=_FULL_NAME_MAX_LEN,
        examples=["Lovelace Ada"],
    )
    email: str = Field(
        description=(
            f"{_MASKED_EMAIL_DESCRIPTION} May be an empty string in "
            "the rare placeholder case where the reader could not "
            "join the underlying user row — the SPA must tolerate "
            "this and fall back to ``full_name`` for display."
        ),
        max_length=EMAIL_MAX_LEN,
        examples=["a*****a@example.com"],
    )

    @classmethod
    def from_view(cls, view: UserRefView) -> Self:
        """Build the schema from a :class:`UserRefView` projection.

        Collapses the name parts via :func:`build_full_name` and
        masks the raw email via :func:`mask_email`. When the view
        carries an empty email (defensive placeholder for rows the
        reader could not join), the masked field is also empty.
        """
        return cls(
            oid=view.oid,
            full_name=build_full_name(
                view.first_name, view.last_name, view.patronymic
            ),
            email=mask_email(view.email) if view.email else "",
        )


class HealthSchema(BaseModel):
    """Liveness response for `GET /healthcheck`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "ok"}]},
    )

    status: str = Field(
        description='Always the literal string `"ok"` when the API is up.',
        examples=["ok"],
    )


class WelcomeSchema(BaseModel):
    """Welcome banner for `GET /`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"message": "Welcome to Learnic's API"}],
        },
    )

    message: str = Field(
        description="Human-readable welcome string. Stable for monitoring.",
        examples=["Welcome to Learnic's API"],
    )
