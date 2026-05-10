import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.role.constants import (
    ROLE_DESCRIPTION_MAX_LEN,
    ROLE_NAME_MAX_LEN,
)
from learnic.entities.role.models import Role
from learnic.entities.role.value_objects import (
    RoleDescription,
    RoleName,
    RolePosition,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


roles_table = sa.Table(
    "roles",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("name", sa.String(ROLE_NAME_MAX_LEN), nullable=False),
    sa.Column(
        "description",
        sa.String(ROLE_DESCRIPTION_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "position",
        sa.Integer,
        nullable=False,
    ),
    sa.Column(
        "created_by",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "product_id",
        "name",
        name="uq_roles_name_per_product",
    ),
    sa.Index("ix_roles_product_id", "product_id"),
)


role_permissions_table = sa.Table(
    "role_permissions",
    mapper_registry.metadata,
    sa.Column(
        "role_id",
        sa.Uuid,
        sa.ForeignKey("roles.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "permission",
        sa.String(64),
        primary_key=True,
    ),
)


_role_mapped = False


def map_role_table() -> None:
    """Apply imperative mapping from :class:`Role` to ``roles_table``.

    The ``permissions`` field is intentionally NOT mapped — it is
    loaded out-of-band by :class:`RoleMapperAlchemy` from
    :data:`role_permissions_table`, mirroring how
    :class:`Product.webinar_details` is handled. The class-level
    default keeps the attribute accessible on freshly hydrated
    instances; the gateway always populates it before returning.
    """
    global _role_mapped  # noqa: PLW0603
    if _role_mapped:
        return
    mapper_registry.map_imperatively(
        Role,
        roles_table,
        properties={
            "oid": roles_table.c.oid,
            "product_id": roles_table.c.product_id,
            "name": composite(RoleName, roles_table.c.name),
            "description": composite(
                RoleDescription.of_optional,
                roles_table.c.description,
            ),
            "position": composite(RolePosition, roles_table.c.position),
            "created_by": roles_table.c.created_by,
            "created_at": roles_table.c.created_at,
            "updated_at": roles_table.c.updated_at,
        },
        column_prefix="_col_",
    )
    _role_mapped = True
