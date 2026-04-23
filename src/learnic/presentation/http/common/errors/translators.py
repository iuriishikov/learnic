"""Translators for converting domain/app errors into HTTP response bodies.

Each translator produces a Pydantic/dataclass model which
``fastapi-error-map`` then serializes via ``jsonable_encoder``. The
response shape matches what the previous global exception handlers
produced so clients keep seeing the same payload.
"""

from pydantic import BaseModel, ConfigDict
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

    ``error`` is the raw class name (``WeakPasswordError``, ``NameTooLongError``,
    ...). Subclass-specific public attributes (e.g. ``reason``, ``field``,
    ``limit``) come through as extra fields.
    """

    model_config = ConfigDict(extra="allow")

    error: str


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


class EntityNotFoundResponseModel(BaseModel):
    error: str
    entity_id: str


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
