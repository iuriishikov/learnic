"""Schemas shared between multiple routers at the HTTP boundary.

Every field carries an OpenAPI-visible ``description`` and at least one
``example``. Length limits mirror the ``constants.py`` of the matching
aggregate so the generated client validates the same invariants the
domain enforces.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from learnic.application.queries.user.get import UserOutput
from learnic.entities.user.constants import (
    DESCRIPTION_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PATRONYMIC_MAX_LEN,
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

    `email` is intentionally omitted — it is private to the account
    owner and never returned by user-facing endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "550e8400-e29b-41d4-a716-446655440000",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "patronymic": None,
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
    first_name: str = Field(
        description="User's given name. Required, non-empty.",
        min_length=1,
        max_length=FIRST_NAME_MAX_LEN,
        examples=["Ada"],
    )
    last_name: str = Field(
        description="User's family name. Required, non-empty.",
        min_length=1,
        max_length=LAST_NAME_MAX_LEN,
        examples=["Lovelace"],
    )
    patronymic: str | None = Field(
        description=(
            "User's middle/patronymic name. `null` when the user has not set one."
        ),
        max_length=PATRONYMIC_MAX_LEN,
        examples=[None, "Augusta"],
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
            first_name=view.first_name,
            last_name=view.last_name,
            patronymic=view.patronymic,
            description=view.description,
            avatar_url=view.avatar_url,
            cover_url=view.cover_url,
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
