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
    BlogPostSlugAlreadyTakenError,
    CannotEnrollInUnpublishedProductError,
    CannotGiftToOwnerError,
    CannotInviteOwnerError,
    CollaborationAlreadyExistsError,
    EmailInviteRateLimitExceededError,
    EmailSendRateLimitExceededError,
    EntityNotFoundError,
    GiftAlreadyExistsError,
    InsufficientPermissionsError,
    InvalidTokenError,
    InviteEmailMismatchError,
    NotAdminError,
    NotResourceOwnerError,
    ProductNotGiftableError,
    RoleInUseError,
    RoleNameAlreadyTakenError,
)
from learnic.entities.common.errors import FieldError
from learnic.entities.common.limits import ResourceLimitReachedError
from learnic.entities.product_collaboration.errors import (
    OperationNotAllowedInStatusError,
)
from learnic.entities.product_gift.errors import (
    InviteTokenExpiredError,
    InviteTokenMismatchError,
    OperationNotAllowedInGiftStatusError,
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
    ResourceLimitTranslator,
)

_named: Final = NamedErrorTranslator()
_field: Final = FieldErrorTranslator()
_not_found: Final = EntityNotFoundTranslator()
_rate_limited: Final = RateLimitedTranslator()
_resource_limit: Final = ResourceLimitTranslator()

FIELD_ERROR_RULE: Final[Rule] = rule(
    status=HTTPStatus.UNPROCESSABLE_ENTITY,
    translator=_field,
)

RESOURCE_LIMIT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_resource_limit,
)
"""409 with body ``{"error": "ResourceLimitReached", "resource": str,
"limit": int}`` — a per-parent count cap (blocks per lesson, products
per author, experiences per user, …) was hit. Not a 429: retrying
won't help until something is deleted."""

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

ACCOUNT_BANNED_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
    translator=_named,
)

NOT_ADMIN_RULE: Final[Rule] = rule(
    status=HTTPStatus.FORBIDDEN,
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

CROSS_NOTE_LESSON_MOVE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

WRONG_BLOCK_TYPE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

WRONG_FILE_CONTENT_TYPE_RULE: Final[Rule] = rule(
    status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    translator=_field,
)
"""Body shape: ``{"error": "WrongFileContentType", "file_id": ...,
"expected_prefix": "video/"|"image/", "actual": "<mime>"}`` — the SPA
can render a precise "this file isn't a video/image" message and offer
a re-upload with the right type."""

STORAGE_QUOTA_EXCEEDED_RULE: Final[Rule] = rule(
    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    translator=_field,
)
"""Body shape: ``{"error": "StorageQuotaExceeded", "plan_code": "FREE",
"used_bytes": ..., "attempted_bytes": ..., "limit_bytes": ...}`` —
enough for the SPA to render "0.4 GB attempted on a 2 GB FREE plan,
1.7 GB already used" and a clear upgrade CTA."""

CANNOT_PUBLISH_NOTE_DIRECTLY_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

CANNOT_ENROLL_IN_UNRELEASED_NOTE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

CANNOT_ENROLL_IN_UNPUBLISHED_PRODUCT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""Body shape: ``{"error": "CannotEnrollInUnpublishedProduct",
"product_id": ..., "status": "draft"|"archived"}`` — the SPA
can tell the user *why* the self-enroll was rejected (draft vs.
archived) and decide whether to surface a "note not yet
available" CTA or hide the action entirely."""

CANNOT_ENROLL_IN_PRIVATE_PRODUCT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)
"""409 ``{"error": "CannotEnrollInPrivateProduct"}`` — self-enroll was
attempted on a private (invite-only) product. The SPA should hide the
self-enroll CTA for private products and surface gift/invite access
instead."""

PRODUCT_DOES_NOT_SUPPORT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""Replaces the legacy ``NOT_A_NOTE_RULE`` / ``NOT_A_WEBINAR_RULE``.

Body shape: ``{"error": "ProductDoesNotSupport", "product_id": ...,
"product_type": "note"|"webinar", "capability": "<capability>"}`` —
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

ENROLLMENT_DOES_NOT_SUPPORT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""Body shape: ``{"error": "EnrollmentDoesNotSupport",
"enrollment_id": ..., "enrollment_kind": "note",
"capability": "<capability>"}`` — mirrors
:data:`PRODUCT_DOES_NOT_SUPPORT_RULE` so the SPA can branch on
which enrollment kind is missing which capability."""

CANNOT_REPIN_REVOKED_ENROLLMENT_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""Body shape: ``{"error": "CannotRepinRevokedEnrollment",
"enrollment_id": ..., "status": "revoked"}`` — re-pin was
attempted on a non-ACTIVE enrollment."""

AUTHENTICATED_MAP: Final[dict[type[Exception], int | Rule]] = {
    InvalidTokenError: INVALID_TOKEN_RULE,
    EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
}

# Base preset for admin-only routes: the access cookie must validate
# (401), the caller must carry the platform-admin flag (403), and the
# targeted entity must exist (404). Admin auth runs through
# ``AdminAuthenticator`` which raises ``InvalidTokenError`` /
# ``NotAdminError``.
ADMIN_MAP: Final[dict[type[Exception], int | Rule]] = {
    InvalidTokenError: INVALID_TOKEN_RULE,
    NotAdminError: NOT_ADMIN_RULE,
    EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
}

# --------------------------------- blog -------------------------------- #

BLOG_POST_SLUG_TAKEN_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)
"""409 ``{"error": "BlogPostSlugAlreadyTaken"}`` — the requested slug
is already used by another post (slugs form the public URL and are
globally unique)."""

BLOG_POST_STATUS_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""409 ``{"error": "BlogPostStatusTransitionError", "status": "...",
"operation": "publish"|"unpublish"}`` — an invalid lifecycle
transition (publishing an already-published post, or unpublishing a
draft)."""

# Base preset for admin blog-post writes: admin auth (401/403), target
# existence (404), plus value-object violations (422).
BLOG_ADMIN_FIELD_MAP: Final[dict[type[Exception], int | Rule]] = {
    **ADMIN_MAP,
    FieldError: FIELD_ERROR_RULE,
}

# Slug-mutating writes (create / change-slug) add the uniqueness 409.
BLOG_ADMIN_SLUG_MAP: Final[dict[type[Exception], int | Rule]] = {
    **BLOG_ADMIN_FIELD_MAP,
    BlogPostSlugAlreadyTakenError: BLOG_POST_SLUG_TAKEN_RULE,
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
    ResourceLimitReachedError: RESOURCE_LIMIT_RULE,
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

EMAIL_SEND_RATE_LIMIT_RULE: Final[Rule] = rule(
    status=HTTPStatus.TOO_MANY_REQUESTS,
    translator=_rate_limited,
)
"""429 with body ``{"error": "EmailSendRateLimitExceeded", "limit":
int, "retry_after_seconds": int}`` — the cross-flow per-user
outbound-email cap enforced by ``EmailSendRateLimiter``. Distinct from
``EMAIL_INVITE_RATE_LIMIT_RULE`` (invite/gift-only cap), but shares the
same response shape."""

COLLABORATION_INVITE_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    CannotInviteOwnerError: CANNOT_INVITE_OWNER_RULE,
    CollaborationAlreadyExistsError: COLLABORATION_ALREADY_EXISTS_RULE,
    RoleHierarchyViolationError: ROLE_HIERARCHY_VIOLATION_RULE,
    EmailInviteRateLimitExceededError: EMAIL_INVITE_RATE_LIMIT_RULE,
    EmailSendRateLimitExceededError: EMAIL_SEND_RATE_LIMIT_RULE,
    ResourceLimitReachedError: RESOURCE_LIMIT_RULE,
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
    EmailSendRateLimitExceededError: EMAIL_SEND_RATE_LIMIT_RULE,
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
    OperationNotAllowedInStatusError: OPERATION_NOT_ALLOWED_IN_STATUS_RULE,
}

# ------------------------------- gifts --------------------------------- #

CANNOT_GIFT_TO_OWNER_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

GIFT_ALREADY_EXISTS_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)

PRODUCT_NOT_GIFTABLE_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""409 with body ``{"error": "ProductNotGiftable", "product_id": ...,
"product_type": "webinar"}`` — only note products can be gifted."""

GIFT_TOKEN_ERROR_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_named,
)
"""409 ``{"error": "InviteTokenMismatch"|"InviteTokenExpired"}`` — the
gift accept token did not match the stored hash or its TTL elapsed."""

GIFT_OPERATION_NOT_ALLOWED_RULE: Final[Rule] = rule(
    status=HTTPStatus.CONFLICT,
    translator=_field,
)
"""409 ``{"error": "OperationNotAllowedInGiftStatusError", "status":
"...", "operation": "..."}`` — accept/decline/revoke attempted on a
gift in a status that forbids it (already accepted/declined/revoked)."""

GIFT_INVITE_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    CannotGiftToOwnerError: CANNOT_GIFT_TO_OWNER_RULE,
    GiftAlreadyExistsError: GIFT_ALREADY_EXISTS_RULE,
    ProductNotGiftableError: PRODUCT_NOT_GIFTABLE_RULE,
    CannotEnrollInUnpublishedProductError: (
        CANNOT_ENROLL_IN_UNPUBLISHED_PRODUCT_RULE
    ),
    EmailInviteRateLimitExceededError: EMAIL_INVITE_RATE_LIMIT_RULE,
    EmailSendRateLimitExceededError: EMAIL_SEND_RATE_LIMIT_RULE,
}

GIFT_ACCEPT_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_WITH_FIELD_MAP,
    NotResourceOwnerError: NOT_RESOURCE_OWNER_RULE,
    InviteEmailMismatchError: INVITE_EMAIL_MISMATCH_RULE,
    CannotEnrollInUnpublishedProductError: (
        CANNOT_ENROLL_IN_UNPUBLISHED_PRODUCT_RULE
    ),
    OperationNotAllowedInGiftStatusError: GIFT_OPERATION_NOT_ALLOWED_RULE,
    InviteTokenMismatchError: GIFT_TOKEN_ERROR_RULE,
    InviteTokenExpiredError: GIFT_TOKEN_ERROR_RULE,
}

GIFT_REVOKE_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    OperationNotAllowedInGiftStatusError: GIFT_OPERATION_NOT_ALLOWED_RULE,
}

GIFT_GET_MAP: Final[dict[type[Exception], int | Rule]] = {
    **AUTHENTICATED_MAP,
    NotResourceOwnerError: NOT_RESOURCE_OWNER_RULE,
}

