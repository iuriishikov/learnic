"""add product collaboration and role tables

Adds the role catalog and the product collaboration / grant
infrastructure used by the per-product authorization model
(``Authorizer`` + ``ProductCollaboration``). Seeds the four
system roles (Viewer / Commentor / Editor / Moderator) with
fixed UUIDs so the application can refer to them by id.

Revision ID: e1b9c4d72a08
Revises: d4a8f7c12e90
Create Date: 2026-05-07 00:00:00.000000

"""

import uuid
from typing import Sequence, TypedDict, Union

import sqlalchemy as sa
from alembic import op


class _SystemRole(TypedDict):
    oid: uuid.UUID
    name: str
    description: str
    permissions: tuple[str, ...]


revision: str = "e1b9c4d72a08"
down_revision: Union[str, Sequence[str], None] = "d4a8f7c12e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_COMMENTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_MODERATOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")


_SYSTEM_ROLES: tuple[_SystemRole, ...] = (
    {
        "oid": _VIEWER_ID,
        "name": "Viewer",
        "description": "Read-only access to the product.",
        "permissions": ("read_product",),
    },
    {
        "oid": _COMMENTOR_ID,
        "name": "Commentor",
        "description": "Read access plus the ability to leave comments.",
        "permissions": ("read_product", "comment"),
    },
    {
        "oid": _EDITOR_ID,
        "name": "Editor",
        "description": (
            "Edit product content (description, cover, modules, "
            "lessons, and Q&A). Cannot publish, archive, or manage "
            "collaborators."
        ),
        "permissions": (
            "read_product",
            "comment",
            "edit_description",
            "edit_cover",
            "edit_modules",
            "edit_lessons",
            "edit_qa",
        ),
    },
    {
        "oid": _MODERATOR_ID,
        "name": "Moderator",
        "description": (
            "Editor permissions plus release management, "
            "publish/archive, and collaborator management."
        ),
        "permissions": (
            "read_product",
            "comment",
            "edit_description",
            "edit_cover",
            "edit_modules",
            "edit_lessons",
            "edit_qa",
            "manage_releases",
            "manage_collaborators",
            "publish",
            "archive",
        ),
    },
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "roles",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("system", "custom", name="role_kind"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_roles_product_id",
        "roles",
        ["product_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_roles_name_per_product "
        "ON roles ("
        "COALESCE(product_id, '00000000-0000-0000-0000-000000000000'), "
        "name)",
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission"),
    )

    op.create_table(
        "product_collaborations",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("collaborator_id", sa.Uuid(), nullable=True),
        sa.Column("invited_email", sa.String(length=320), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending_invite",
                "active",
                "revoked",
                name="product_collaboration_status",
            ),
            nullable=False,
        ),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column(
            "invite_token_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "invite_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["collaborator_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "invite_token_hash",
            name="uq_collab_invite_token_hash",
        ),
    )
    op.create_index(
        "ix_collab_collaborator_id",
        "product_collaborations",
        ["collaborator_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_collab_product_collaborator_active "
        "ON product_collaborations (product_id, collaborator_id) "
        "WHERE collaborator_id IS NOT NULL "
        "AND status <> 'revoked'",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_collab_product_email_pending "
        "ON product_collaborations (product_id, invited_email) "
        "WHERE invited_email IS NOT NULL "
        "AND status = 'pending_invite'",
    )

    op.create_table(
        "collaboration_grants",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("collaboration_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "scope_type",
            sa.Enum(
                "product",
                "module",
                "lesson",
                name="collaboration_scope_type",
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["product_collaborations.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_grant_collaboration_id",
        "collaboration_grants",
        ["collaboration_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_grant_unique_scope "
        "ON collaboration_grants ("
        "collaboration_id, scope_type, "
        "COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'))",
    )

    _seed_system_roles()


def _seed_system_roles() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("oid", sa.Uuid()),
        sa.column("product_id", sa.Uuid()),
        sa.column(
            "kind",
            sa.Enum("system", "custom", name="role_kind", create_type=False),
        ),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("created_by", sa.Uuid()),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission", sa.String()),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "oid": role["oid"],
                "product_id": None,
                "kind": "system",
                "name": role["name"],
                "description": role["description"],
                "created_by": None,
            }
            for role in _SYSTEM_ROLES
        ],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": role["oid"], "permission": permission}
            for role in _SYSTEM_ROLES
            for permission in role["permissions"]
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_grant_unique_scope",
        table_name="collaboration_grants",
    )
    op.drop_index(
        "ix_grant_collaboration_id",
        table_name="collaboration_grants",
    )
    op.drop_table("collaboration_grants")

    op.drop_index(
        "uq_collab_product_email_pending",
        table_name="product_collaborations",
    )
    op.drop_index(
        "uq_collab_product_collaborator_active",
        table_name="product_collaborations",
    )
    op.drop_index(
        "ix_collab_collaborator_id",
        table_name="product_collaborations",
    )
    op.drop_table("product_collaborations")

    op.drop_table("role_permissions")
    op.drop_index("uq_roles_name_per_product", table_name="roles")
    op.drop_index("ix_roles_product_id", table_name="roles")
    op.drop_table("roles")

    op.execute("DROP TYPE collaboration_scope_type")
    op.execute("DROP TYPE product_collaboration_status")
    op.execute("DROP TYPE role_kind")
