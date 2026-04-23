"""Pre-composed error rules for reuse across routes.

Each rule bundles an HTTP status code with a translator. Routes
declare ``error_map={DomainException: <RULE>}`` to keep route-level
decorators concise and consistent.

This module also exposes ready-made ``error_map`` presets (``*_MAP``)
for the combinations that repeat across routes. Extend them with
dict-merge (``| {ExtraError: RULE}``) when a route needs more.
"""

from http import HTTPStatus
from typing import Final

from fastapi_error_map import rule
from fastapi_error_map.rules import Rule

from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidTokenError,
)
from learnic.entities.common.errors import FieldError
from learnic.presentation.http.common.errors.translators import (
    EntityNotFoundTranslator,
    FieldErrorTranslator,
    NamedErrorTranslator,
)

_named: Final = NamedErrorTranslator()
_field: Final = FieldErrorTranslator()
_not_found: Final = EntityNotFoundTranslator()

FIELD_ERROR_RULE: Final[Rule] = rule(
    status=HTTPStatus.UNPROCESSABLE_ENTITY,
    translator=_field,
)

ENTITY_NOT_FOUND_RULE: Final[Rule] = rule(
    status=HTTPStatus.NOT_FOUND,
    translator=_not_found,
)

INVALID_CREDENTIALS_RULE: Final[Rule] = rule(
    status=HTTPStatus.UNAUTHORIZED,
    translator=_named,
)

INVALID_TOKEN_RULE: Final[Rule] = rule(
    status=HTTPStatus.UNAUTHORIZED,
    translator=_named,
)

EMAIL_ALREADY_REGISTERED_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

EMAIL_NOT_VERIFIED_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

AUTHENTICATED_MAP: Final[dict[type[Exception], int | Rule]] = {
    InvalidTokenError: INVALID_TOKEN_RULE,
    EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
}

AUTHENTICATED_WITH_FIELD_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_MAP,
    FieldError: FIELD_ERROR_RULE,
}
