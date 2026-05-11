from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Permission(StrEnum):
    """Flat catalog of authorized actions on a product.

    Permissions are checked by :class:`Authorizer` against a
    collaborator's effective grants. Implication relationships
    and valid scope levels live together in :data:`_PERMISSION_META`
    (one record per :class:`Permission` value); the module-load
    ``assert`` below guarantees every enum value has a matching
    record so a missed entry fails at startup, not in a later
    authorization check.
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


@dataclass(frozen=True, slots=True)
class _PermissionMeta:
    """Per-permission metadata kept in one record.

    Attributes:
        implies: Permissions transitively granted alongside this one
            (e.g. ``EDIT_MODULES`` implies ``READ_PRODUCT`` and
            ``EDIT_LESSONS``). Resolved at authorization time via
            :func:`expand_implied`.
        targets: Scope levels at which a grant of this permission
            makes sense (e.g. ``PUBLISH`` only at ``PRODUCT`` scope;
            ``EDIT_LESSONS`` at any scope). Validated at grant
            creation time, not at authorization time.
    """

    implies: frozenset[Permission]
    targets: frozenset[ScopeType]


_ALL_SCOPES: Final = frozenset(
    {ScopeType.PRODUCT, ScopeType.MODULE, ScopeType.LESSON},
)
_PRODUCT_ONLY: Final = frozenset({ScopeType.PRODUCT})


# Single source of truth: every Permission's transitive closure +
# valid scopes live in one record. New permissions go here; the
# module-load assertions below catch any forgotten entry.
_PERMISSION_META: Final[dict[Permission, _PermissionMeta]] = {
    Permission.READ_PRODUCT: _PermissionMeta(
        implies=frozenset(),
        targets=_ALL_SCOPES,
    ),
    Permission.COMMENT: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_ALL_SCOPES,
    ),
    Permission.EDIT_DESCRIPTION: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.EDIT_COVER: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.EDIT_MODULES: _PermissionMeta(
        implies=frozenset(
            {Permission.READ_PRODUCT, Permission.EDIT_LESSONS},
        ),
        targets=frozenset({ScopeType.PRODUCT, ScopeType.MODULE}),
    ),
    Permission.EDIT_LESSONS: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_ALL_SCOPES,
    ),
    Permission.EDIT_QA: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.MANAGE_RELEASES: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.MANAGE_COLLABORATORS: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.MANAGE_ROLES: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.PUBLISH: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
    Permission.ARCHIVE: _PermissionMeta(
        implies=frozenset({Permission.READ_PRODUCT}),
        targets=_PRODUCT_ONLY,
    ),
}


# Fail-fast: any Permission without a metadata entry crashes the
# process at import time, not in a later authorization check.
_missing_meta = set(Permission) - set(_PERMISSION_META)
if _missing_meta:
    raise RuntimeError(
        "_PERMISSION_META is incomplete; missing entries for: "
        f"{sorted(p.value for p in _missing_meta)}",
    )

# Reject self-imply: silently breaks the transitive-closure intent
# without :func:`expand_implied` ever noticing (it deduplicates).
for _perm, _meta in _PERMISSION_META.items():
    if _perm in _meta.implies:
        raise RuntimeError(
            f"{_perm.value} must not imply itself in _PERMISSION_META",
        )


def permission_meta(permission: Permission) -> _PermissionMeta:
    """Return the metadata record for ``permission``.

    Preferred over reading :data:`PERMISSION_IMPLIES` /
    :data:`PERMISSION_TARGETS` directly so that future metadata
    (description, category, default-in-role flag, …) can be added
    without touching call sites.
    """
    return _PERMISSION_META[permission]


# Back-compat views — derived once at import; callers that read the
# dicts (tests, validators) keep working without migration.
PERMISSION_IMPLIES: Final[dict[Permission, frozenset[Permission]]] = {
    p: m.implies for p, m in _PERMISSION_META.items()
}

PERMISSION_TARGETS: Final[dict[Permission, frozenset[ScopeType]]] = {
    p: m.targets for p, m in _PERMISSION_META.items()
}


def expand_implied(
    permissions: frozenset[Permission],
) -> frozenset[Permission]:
    """Return the transitive closure of ``permissions``.

    Used at authorization time to resolve effective permissions
    before answering a ``require(...)`` check.
    """
    expanded: set[Permission] = set(permissions)
    pending: list[Permission] = list(permissions)
    while pending:
        current = pending.pop()
        for implied in _PERMISSION_META[current].implies:
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return frozenset(expanded)
