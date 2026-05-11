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
    CannotInviteOwnerError,
    CollaborationAlreadyExistsError,
    EmailInviteRateLimitExceededError,
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidTokenError,
    InviteEmailMismatchError,
    NotResourceOwnerError,
    RoleInUseError,
    RoleNameAlreadyTakenError,
)
from learnic.entities.common.errors import FieldError
from learnic.entities.product_collaboration.errors import (
    OperationNotAllowedInStatusError,
)
from learnic.entities.role.errors import (
    CannotGrantPermissionsBeyondOwnSetError,
    RoleHierarchyViolationError,
)
from learnic.presentation.http.common.errors.translators import (
    EntityNotFoundTranslator,
    FieldErrorTranslator,
    NamedErrorTranslator,
    RateLimitedTranslator,
)

_named: Final = NamedErrorTranslator()
_field: Final = FieldErrorTranslator()
_not_found: Final = EntityNotFoundTranslator()
_rate_limited: Final = RateLimitedTranslator()

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

USER_AVATAR_NOT_FOUND_RULE: Final[Rule] = rule(
    status=HTTPStatus.NOT_FOUND,
    translator=_named,
)

USER_COVER_NOT_FOUND_RULE: Final[Rule] = rule(
    status=HTTPStatus.NOT_FOUND,
    translator=_named,
)

NOT_RESOURCE_OWNER_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

PRODUCT_NOT_IN_DRAFT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

PRODUCT_NOT_ARCHIVED_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

PRODUCT_NAME_TAKEN_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

INVALID_REORDER_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

CROSS_COURSE_LESSON_MOVE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

WRONG_BLOCK_TYPE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

CANNOT_PUBLISH_COURSE_DIRECTLY_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

CANNOT_ENROLL_IN_UNRELEASED_COURSE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

PRODUCT_DOES_NOT_SUPPORT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""Replaces the legacy ``NOT_A_COURSE_RULE`` / ``NOT_A_WEBINAR_RULE``.

Body shape: ``{"error": "ProductDoesNotSupport", "product_id": ...,
"product_type": "course"|"webinar", "capability": "<capability>"}`` —
the SPA can render a precise "this operation isn't available for X
products" message without parsing free-form text.
"""

ENROLLMENT_CLOSED_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

ALREADY_ENROLLED_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

COHORT_FULL_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

AUTHENTICATED_MAP: Final[dict[type[Exception], int | Rule]] = {
    InvalidTokenError: INVALID_TOKEN_RULE,
    EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
}

INSUFFICIENT_PERMISSIONS_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

AUTHENTICATED_WITH_FIELD_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_MAP,
    FieldError: FIELD_ERROR_RULE,
}

AUTHENTICATED_OWNER_FIELD_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_WITH_FIELD_MAP,
    NotResourceOwnerError: NOT_RESOURCE_OWNER_RULE,
    InsufficientPermissionsError: INSUFFICIENT_PERMISSIONS_RULE,
}

CANNOT_INVITE_OWNER_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

COLLABORATION_ALREADY_EXISTS_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

ROLE_IN_USE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

ROLE_NAME_TAKEN_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

INVITE_EMAIL_MISMATCH_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

ROLE_HIERARCHY_VIOLATION_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

PERM_BEYOND_OWN_SET_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

AUTHENTICATED_AUTHORIZED_FIELD_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_WITH_FIELD_MAP,
    InsufficientPermissionsError: INSUFFICIENT_PERMISSIONS_RULE,
}

# Default for editing routes that previously gated on owner-only via
# ``NotResourceOwnerError``. Now both errors are mapped to 403 — the
# Authorizer raises ``InsufficientPermissions`` for non-owner non-permitted
# callers, while a handful of operational handlers (cohort, enrollment)
# still raise ``NotResourceOwnerError`` directly.
EDIT_ROUTE_MAP: Final[dict[type[Exception], int | Rule]] = AUTHENTICATED_OWNER_FIELD_MAP

EMAIL_INVITE_RATE_LIMIT_RULE: Final[Rule] = rule(
    status=HTTPStatus.TOO_MANY_REQUESTS,
    translator=_rate_limited,
)

COLLABORATION_INVITE_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    CannotInviteOwnerError: CANNOT_INVITE_OWNER_RULE,
    CollaborationAlreadyExistsError: COLLABORATION_ALREADY_EXISTS_RULE,
    RoleHierarchyViolationError: ROLE_HIERARCHY_VIOLATION_RULE,
    EmailInviteRateLimitExceededError: EMAIL_INVITE_RATE_LIMIT_RULE,
}

OPERATION_NOT_ALLOWED_IN_STATUS_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""409 with body ``{"error": "OperationNotAllowedInStatusError",
"status": "...", "operation": "..."}`` for any collaboration mutation
forbidden by the state machine (accept/decline/revoke/replace_grants
in the wrong status)."""

COLLABORATION_MUTATION_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    RoleHierarchyViolationError: ROLE_HIERARCHY_VIOLATION_RULE,
    OperationNotAllowedInStatusError: OPERATION_NOT_ALLOWED_IN_STATUS_RULE,
}

ROLE_MUTATION_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    RoleNameAlreadyTakenError: ROLE_NAME_TAKEN_RULE,
    CannotGrantPermissionsBeyondOwnSetError: PERM_BEYOND_OWN_SET_RULE,
}

ROLE_DELETE_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    RoleInUseError: ROLE_IN_USE_RULE,
}

COLLABORATION_ACCEPT_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_WITH_FIELD_MAP,
    NotResourceOwnerError: NOT_RESOURCE_OWNER_RULE,
    InviteEmailMismatchError: INVITE_EMAIL_MISMATCH_RULE,
}
