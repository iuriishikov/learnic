from enum import StrEnum
from typing import Final


class Permission(StrEnum):
    """Flat catalog of authorized actions on a product.

    Permissions are checked by :class:`Authorizer` against a
    collaborator's effective grants. Implication relationships
    live in :data:`PERMISSION_IMPLIES` (e.g. ``EDIT_MODULES``
    transitively grants ``EDIT_LESSONS``); valid scope levels
    live in :data:`PERMISSION_TARGETS` (e.g. ``PUBLISH`` only
    makes sense at product scope).
    """

    READ_PRODUCT = "read_product"
    COMMENT = "comment"
    EDIT_DESCRIPTION = "edit_description"
    EDIT_COVER = "edit_cover"
    EDIT_MODULES = "edit_modules"
    EDIT_LESSONS = "edit_lessons"
    EDIT_QA = "edit_qa"
    MANAGE_RELEASES = "manage_releases"
    MANAGE_COLLABORATORS = "manage_collaborators"
    MANAGE_ROLES = "manage_roles"
    PUBLISH = "publish"
    ARCHIVE = "archive"


class ScopeType(StrEnum):
    """Granularity at which a collaboration grant applies.

    ``PRODUCT`` covers the whole product (and every module/lesson
    inside it). ``MODULE`` covers a single module and all of its
    lessons. ``LESSON`` covers a single lesson only.
    """

    PRODUCT = "product"
    MODULE = "module"
    LESSON = "lesson"


PERMISSION_IMPLIES: Final[dict[Permission, frozenset[Permission]]] = {
    Permission.COMMENT: frozenset({Permission.READ_PRODUCT}),
    Permission.EDIT_DESCRIPTION: frozenset({Permission.READ_PRODUCT}),
    Permission.EDIT_COVER: frozenset({Permission.READ_PRODUCT}),
    Permission.EDIT_MODULES: frozenset(
        {Permission.READ_PRODUCT, Permission.EDIT_LESSONS},
    ),
    Permission.EDIT_LESSONS: frozenset({Permission.READ_PRODUCT}),
    Permission.EDIT_QA: frozenset({Permission.READ_PRODUCT}),
    Permission.MANAGE_RELEASES: frozenset({Permission.READ_PRODUCT}),
    Permission.MANAGE_COLLABORATORS: frozenset({Permission.READ_PRODUCT}),
    Permission.MANAGE_ROLES: frozenset({Permission.READ_PRODUCT}),
    Permission.PUBLISH: frozenset({Permission.READ_PRODUCT}),
    Permission.ARCHIVE: frozenset({Permission.READ_PRODUCT}),
}


PERMISSION_TARGETS: Final[dict[Permission, frozenset[ScopeType]]] = {
    Permission.READ_PRODUCT: frozenset(
        {ScopeType.PRODUCT, ScopeType.MODULE, ScopeType.LESSON},
    ),
    Permission.COMMENT: frozenset(
        {ScopeType.PRODUCT, ScopeType.MODULE, ScopeType.LESSON},
    ),
    Permission.EDIT_DESCRIPTION: frozenset({ScopeType.PRODUCT}),
    Permission.EDIT_COVER: frozenset({ScopeType.PRODUCT}),
    Permission.EDIT_MODULES: frozenset(
        {ScopeType.PRODUCT, ScopeType.MODULE},
    ),
    Permission.EDIT_LESSONS: frozenset(
        {ScopeType.PRODUCT, ScopeType.MODULE, ScopeType.LESSON},
    ),
    Permission.EDIT_QA: frozenset({ScopeType.PRODUCT}),
    Permission.MANAGE_RELEASES: frozenset({ScopeType.PRODUCT}),
    Permission.MANAGE_COLLABORATORS: frozenset({ScopeType.PRODUCT}),
    Permission.MANAGE_ROLES: frozenset({ScopeType.PRODUCT}),
    Permission.PUBLISH: frozenset({ScopeType.PRODUCT}),
    Permission.ARCHIVE: frozenset({ScopeType.PRODUCT}),
}


def expand_implied(permissions: frozenset[Permission]) -> frozenset[Permission]:
    """Return the transitive closure of ``permissions`` under :data:`PERMISSION_IMPLIES`.

    Used at authorization time to resolve effective permissions
    before answering a ``require(...)`` check.
    """
    expanded: set[Permission] = set(permissions)
    pending: list[Permission] = list(permissions)
    while pending:
        current = pending.pop()
        for implied in PERMISSION_IMPLIES.get(current, frozenset()):
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return frozenset(expanded)
