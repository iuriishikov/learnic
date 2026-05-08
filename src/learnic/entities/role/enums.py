from enum import StrEnum


class RoleKind(StrEnum):
    """Origin of a role definition.

    ``SYSTEM`` roles are seeded by Alembic and shared across all
    products; they cannot be renamed, edited, or deleted via the
    public API. ``CUSTOM`` roles are created by a product's
    collaborators (with ``MANAGE_ROLES``) and live only inside that
    product.
    """

    SYSTEM = "system"
    CUSTOM = "custom"
