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
    PORTFOLIO_URL_MAX_LEN,
    PUBLIC_EMAIL_MAX_LEN,
    WEBSITE_URL_MAX_LEN,
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
    """Reference to a file resource with a ready-to-use presigned URL.

    Surfaced everywhere the API embeds a file — avatars, covers,
    user-experience icons, lesson-block uploads. The ``url`` is a
    short-lived presigned-storage URL: the SPA renders it directly
    with ``<img>`` / ``<video>`` / download links, no extra round-
    trip needed. Re-fetch the parent resource to refresh the URL
    when it expires (the URL's TTL is implementation-defined and
    typically 1 hour).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "content_type": "image/jpeg",
                    "size_bytes": 184_320,
                    "url": (
                        "https://s3.example.com/learnic/avatars/"
                        "ada.jpg?X-Amz-Signature=..."
                    ),
                },
            ],
        },
    )

    oid: UUID = Field(
        description=(
            "Server-generated UUID identifying the stored file. Stable "
            "across requests; use it for client-side cache keys."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    content_type: str = Field(
        description=(
            "MIME type recorded at upload time. Useful when the same "
            "field can hold multiple types (a lesson-file block accepts "
            "PDFs, archives, slide decks — the SPA branches on the "
            "type to render a preview or a download tile)."
        ),
        examples=["image/jpeg", "video/mp4", "application/pdf"],
    )
    size_bytes: int = Field(
        description=(
            "Stored size in bytes. Surfaced so the SPA can render a "
            "human-readable size next to the file without a separate "
            "HEAD request."
        ),
        ge=1,
        examples=[184_320, 52_428_800],
    )
    url: str = Field(
        description=(
            "Short-lived presigned-storage URL. Browser clients fetch "
            "it directly via `<img>` / `<video>` / download links. "
            "The URL expires; re-fetch the parent resource to get a "
            "fresh one."
        ),
        examples=[
            "https://s3.example.com/learnic/avatars/ada.jpg?X-Amz-Signature=...",
        ],
    )


class UploadedFileSchema(BaseModel):
    """Confirmation envelope returned by file-upload endpoints.

    Carries only the freshly-created file's id. The full
    :class:`FileSchema` with presigned URL is delivered by the parent
    resource (avatar / cover lives on :class:`UserSchema`, product
    cover on :class:`ProductSchema`, etc.) — the client should
    refetch that resource after upload rather than locking onto a
    URL the upload response would have to sign in advance.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "550e8400-e29b-41d4-a716-446655440000"},
            ],
        },
    )

    oid: UUID = Field(
        description="Server-generated UUID of the newly stored file.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class UserBaseSchema(BaseModel):
    """Shared identity fields for every public user projection.

    Single source of truth for the fields common to
    :class:`UserSchema` (full profile), :class:`UserSummarySchema`
    (name-search hit), and ``TopTeacherSchema`` (popularity ranking):
    the stable id, the canonical ``Last First Patronymic`` display
    name, the masked login ``email``, the verified badge, and an
    optional avatar thumbnail. Concrete schemas inherit these and add
    their own fields. ``email`` is always masked (see
    :func:`mask_email`) — none of these projections ever return a
    plain login address.
    """

    model_config = ConfigDict(from_attributes=True)

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
    is_verified: bool = Field(
        description=(
            "Whether the platform has granted the user the public "
            "\"verified\" badge — surfaced as a brand-coloured "
            "checkmark on the avatar across the SPA. Distinct from "
            "`email_verified`, which only tracks login-email "
            "confirmation and is not surfaced through this API."
        ),
        examples=[True, False],
    )
    avatar: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved avatar file with a short-lived presigned URL, "
            "or `null` when no avatar is attached. The URL expires; "
            "re-fetch the resource to get a fresh one."
        ),
    )


class UserSchema(UserBaseSchema):
    """Public user profile returned by ``GET /users/{id}``.

    Extends :class:`UserBaseSchema` with the full-profile fields: the
    user-authored ``description``, the ``cover`` image, and the
    optional ``website_url`` / ``portfolio_url`` / ``public_email``
    contact links. The identity fields (id, name, masked email,
    verified badge, avatar) come from the base.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "full_name": "Lovelace Ada",
                    "email": "a*****a@example.com",
                    "is_verified": True,
                    "description": "<p>Mathematician.</p>",
                    "avatar": {
                        "oid": "11111111-2222-3333-4444-555555555555",
                        "content_type": "image/jpeg",
                        "size_bytes": 184_320,
                        "url": (
                            "https://s3.example.com/avatars/"
                            "ada.jpg?X-Amz-Signature=..."
                        ),
                    },
                    "cover": None,
                },
            ],
        },
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
    cover: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved cover image with a short-lived presigned URL, "
            "or `null` when no cover is attached. The URL expires; "
            "re-fetch the user resource to get a fresh one."
        ),
    )
    website_url: str | None = Field(
        description=(
            "User-supplied personal website URL, or `null` when not "
            "set. Always an absolute `http(s)` URL within "
            f"{WEBSITE_URL_MAX_LEN} characters (`WEBSITE_URL_MAX_LEN`)."
        ),
        max_length=WEBSITE_URL_MAX_LEN,
        examples=[None, "https://example.com"],
    )
    portfolio_url: str | None = Field(
        description=(
            "User-supplied portfolio URL, or `null` when not set. "
            "Always an absolute `http(s)` URL within "
            f"{PORTFOLIO_URL_MAX_LEN} characters (`PORTFOLIO_URL_MAX_LEN`)."
        ),
        max_length=PORTFOLIO_URL_MAX_LEN,
        examples=[None, "https://dribbble.com/example"],
    )
    public_email: str | None = Field(
        description=(
            "User-supplied public contact email, or `null` when not "
            "set. Distinct from the login email — surfaced un-masked "
            "because the user explicitly opted in to publishing it. "
            f"Max length is {PUBLIC_EMAIL_MAX_LEN} characters "
            "(`PUBLIC_EMAIL_MAX_LEN`)."
        ),
        max_length=PUBLIC_EMAIL_MAX_LEN,
        examples=[None, "hello@example.com"],
    )

    @classmethod
    def from_view(cls, view: UserOutput) -> Self:
        """Build the schema from a ``GetUserQueryHandler`` output.

        Pydantic does the heavy lifting through ``from_attributes=True``;
        the method exists for caller-side discoverability and stays
        cheap. Use :meth:`model_validate` directly if you prefer.
        """
        return cls.model_validate(view)


class UserSummarySchema(UserBaseSchema):
    """Lightweight user projection returned by name search.

    Adds nothing to :class:`UserBaseSchema`: a search hit is exactly
    the shared identity projection — id, canonical display name,
    masked login email, verified badge, and avatar thumbnail. The
    full profile (description, cover, contact links) is only returned
    by ``GET /users/{id}`` via :class:`UserSchema`.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "full_name": "Lovelace Ada",
                    "email": "a*****a@example.com",
                    "is_verified": True,
                    "avatar": {
                        "oid": "11111111-2222-3333-4444-555555555555",
                        "content_type": "image/jpeg",
                        "size_bytes": 184_320,
                        "url": "https://s3.example.com/avatars/...",
                    },
                },
            ],
        },
    )

    @classmethod
    def from_view(cls, view: UserSummaryOutput) -> Self:
        """Build the schema from a ``SearchUsersQueryHandler`` hit."""
        return cls.model_validate(view)


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
            full_name=build_full_name(view.first_name, view.last_name, view.patronymic),
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
