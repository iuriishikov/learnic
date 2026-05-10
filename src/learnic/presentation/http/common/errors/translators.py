"""Translators for converting domain/app errors into HTTP response bodies.

Each translator produces a Pydantic/dataclass model which
``fastapi-error-map`` then serializes via ``jsonable_encoder``. The
response shape matches what the previous global exception handlers
produced so clients keep seeing the same payload.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import override

from fastapi_error_map import ErrorTranslator, SimpleErrorResponseModel

_ERROR_SUFFIX = "Error"


def _strip_error_suffix(name: str) -> str:
    return name[: -len(_ERROR_SUFFIX)] if name.endswith(_ERROR_SUFFIX) else name


class NamedErrorTranslator(ErrorTranslator[SimpleErrorResponseModel]):
    """``{"error": "<ClassNameWithoutErrorSuffix>"}``.

    Good default for simple domain/application errors that carry no
    extra payload (``InvalidCredentialsError`` → ``"InvalidCredentials"``).
    """

    @property
    @override
    def error_response_model_cls(self) -> type[SimpleErrorResponseModel]:
        return SimpleErrorResponseModel

    @override
    def from_error(self, err: Exception) -> SimpleErrorResponseModel:
        return SimpleErrorResponseModel(
            error=_strip_error_suffix(type(err).__name__),
        )


class FieldErrorResponseModel(BaseModel):
    """Response for a value-object invariant violation.

    ``error`` is the raw class name (``WeakPasswordError``,
    ``NameTooLongError``, ...). Subclass-specific public attributes
    (e.g. ``reason``, ``field``, ``limit``) come through as extra
    fields — clients should treat the body as ``{"error": str, ...}``
    and read whatever extras the specific error class documents.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "error": "FirstNameTooLongError",
                    "field": "first_name",
                    "limit": 100,
                },
                {
                    "error": "WeakPasswordError",
                    "reason": "missing_digit",
                },
                {"error": "InvalidEmailError"},
            ],
        },
    )

    error: str = Field(
        description=(
            "Raw class name of the violated value-object invariant "
            "(e.g. `WeakPasswordError`, `FirstNameTooLongError`). "
            "Always present."
        ),
        examples=["WeakPasswordError"],
    )


class FieldErrorTranslator(ErrorTranslator[FieldErrorResponseModel]):
    """``{"error": "<ClassName>", **public_attrs}`` for ``FieldError``s."""

    @property
    @override
    def error_response_model_cls(self) -> type[FieldErrorResponseModel]:
        return FieldErrorResponseModel

    @override
    def from_error(self, err: Exception) -> FieldErrorResponseModel:
        extras = {k: v for k, v in vars(err).items() if not k.startswith("_")}
        return FieldErrorResponseModel(
            error=type(err).__name__,
            **extras,
        )


class RateLimitedResponseModel(BaseModel):
    """Response for actor-scoped rate-limit violations.

    Carries the ``limit`` that was hit and ``retry_after_seconds``
    so the SPA can render a precise "try again in N hours" message
    without parsing free-form text.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "EmailInviteRateLimitExceeded",
                    "limit": 10,
                    "retry_after_seconds": 86400,
                },
            ],
        },
    )

    error: str = Field(
        description=(
            "Raw class name of the rate-limit error without the "
            "trailing `Error` suffix."
        ),
        examples=["EmailInviteRateLimitExceeded"],
    )
    limit: int = Field(
        description=(
            "Maximum number of operations allowed in the rolling "
            "window before the limit triggers."
        ),
        examples=[10],
    )
    retry_after_seconds: int = Field(
        description=(
            "Hint at how long the caller must wait before retrying. "
            "Mirrors the standard `Retry-After` HTTP header."
        ),
        examples=[86400],
    )


class RateLimitedTranslator(ErrorTranslator[RateLimitedResponseModel]):
    """``{"error": "<ClassName>", "limit": int, "retry_after_seconds": int}``."""

    @property
    @override
    def error_response_model_cls(
        self,
    ) -> type[RateLimitedResponseModel]:
        return RateLimitedResponseModel

    @override
    def from_error(self, err: Exception) -> RateLimitedResponseModel:
        return RateLimitedResponseModel(
            error=_strip_error_suffix(type(err).__name__),
            limit=int(getattr(err, "limit", 0)),
            retry_after_seconds=int(
                getattr(err, "retry_after_seconds", 0),
            ),
        )


class EntityNotFoundResponseModel(BaseModel):
    """Response for a missing aggregate lookup."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "EntityNotFound",
                    "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                },
            ],
        },
    )

    error: str = Field(
        description='Always the literal string `"EntityNotFound"`.',
        examples=["EntityNotFound"],
    )
    entity_id: str = Field(
        description=(
            "String form of the missing entity's id. UUID for "
            "domain aggregates; empty string when the underlying "
            "exception didn't carry an id."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class EntityNotFoundTranslator(ErrorTranslator[EntityNotFoundResponseModel]):
    """``{"error": "EntityNotFound", "entity_id": "<uuid>"}``."""

    @property
    @override
    def error_response_model_cls(
        self,
    ) -> type[EntityNotFoundResponseModel]:
        return EntityNotFoundResponseModel

    @override
    def from_error(self, err: Exception) -> EntityNotFoundResponseModel:
        entity_id = getattr(err, "entity_id", None)
        return EntityNotFoundResponseModel(
            error="EntityNotFound",
            entity_id=str(entity_id) if entity_id is not None else "",
        )
