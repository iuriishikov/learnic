from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_HASH_LEN,
)
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import (
    InviteTokenHash,
)
from learnic.entities.role.permissions import ScopeType
from learnic.entities.user.constants import EMAIL_MAX_LEN
from learnic.entities.user.value_objects import Email
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


product_collaborations_table = sa.Table(
    "product_collaborations",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "collaborator_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=True,
    ),
    sa.Column(
        "invited_email",
        sa.String(EMAIL_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "status",
        sa.Enum(
            CollaborationStatus,
            name="product_collaboration_status",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "invited_by",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "invite_token_hash",
        sa.String(INVITE_TOKEN_HASH_LEN),
        nullable=True,
        unique=True,
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
        "declined_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    sa.Column(
        "revoked_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    sa.Index(
        "uq_collab_product_collaborator_active",
        "product_id",
        "collaborator_id",
        unique=True,
        postgresql_where=sa.and_(
            sa.column("collaborator_id").isnot(None),
            sa.column("status").notin_(
                [
                    CollaborationStatus.REVOKED.value,
                    CollaborationStatus.DECLINED.value,
                ],
            ),
        ),
    ),
    sa.Index(
        "uq_collab_product_email_pending",
        "product_id",
        "invited_email",
        unique=True,
        postgresql_where=sa.and_(
            sa.column("invited_email").isnot(None),
            sa.column("status") == CollaborationStatus.PENDING_INVITE.value,
        ),
    ),
    sa.Index(
        "ix_collab_collaborator_id",
        "collaborator_id",
    ),
)


collaboration_grants_table = sa.Table(
    "collaboration_grants",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "collaboration_id",
        sa.Uuid,
        sa.ForeignKey(
            "product_collaborations.oid",
            ondelete="CASCADE",
        ),
        nullable=False,
    ),
    sa.Column(
        "role_id",
        sa.Uuid,
        # CASCADE (not RESTRICT): in-use roles are blocked from deletion
        # application-side by ``RoleInUseError`` before any DELETE runs,
        # so this FK only fires on a full-note hard-delete or when a role
        # holds nothing but dead (declined/revoked) grants — both of
        # which should sweep the grant rows. RESTRICT aborted the admin
        # note-delete cascade with an IntegrityError. See migration
        # ``notedel0001``.
        sa.ForeignKey("roles.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "scope_type",
        sa.Enum(
            ScopeType,
            name="collaboration_scope_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column("scope_id", sa.Uuid, nullable=True),
    sa.Index(
        "ix_grant_collaboration_id",
        "collaboration_id",
    ),
    sa.Index(
        "uq_grant_unique_scope",
        "collaboration_id",
        "scope_type",
        sa.func.coalesce(
            sa.column("scope_id"),
            sa.literal("00000000-0000-0000-0000-000000000000"),
        ),
        unique=True,
    ),
)


_collaboration_mapped = False
_grant_mapped = False


def map_product_collaboration_table() -> None:
    """Apply imperative mapping for :class:`ProductCollaboration`.

    The ``grants`` field is intentionally NOT mapped — it is loaded
    out-of-band by :class:`ProductCollaborationMapperAlchemy` from
    :data:`collaboration_grants_table`, mirroring how
    :class:`Product.webinar_details` is handled.
    """
    global _collaboration_mapped  # noqa: PLW0603
    if _collaboration_mapped:
        return
    mapper_registry.map_imperatively(
        ProductCollaboration,
        product_collaborations_table,
        properties={
            "oid": product_collaborations_table.c.oid,
            "product_id": product_collaborations_table.c.product_id,
            "collaborator_id": (product_collaborations_table.c.collaborator_id),
            "invited_email": composite(
                Email.of_optional,
                product_collaborations_table.c.invited_email,
            ),
            "status": product_collaborations_table.c.status,
            "invited_by": product_collaborations_table.c.invited_by,
            "invite_token_hash": composite(
                InviteTokenHash.of_optional,
                product_collaborations_table.c.invite_token_hash,
            ),
            "invite_expires_at": (product_collaborations_table.c.invite_expires_at),
            "created_at": product_collaborations_table.c.created_at,
            "accepted_at": product_collaborations_table.c.accepted_at,
            "declined_at": product_collaborations_table.c.declined_at,
            "revoked_at": product_collaborations_table.c.revoked_at,
        },
        column_prefix="_col_",
    )
    _collaboration_mapped = True


def map_collaboration_grant_table() -> None:
    """Apply imperative mapping for :class:`CollaborationGrant`."""
    global _grant_mapped  # noqa: PLW0603
    if _grant_mapped:
        return
    mapper_registry.map_imperatively(
        CollaborationGrant,
        collaboration_grants_table,
        properties={
            "oid": collaboration_grants_table.c.oid,
            "role_id": collaboration_grants_table.c.role_id,
            "scope_type": collaboration_grants_table.c.scope_type,
            "scope_id": collaboration_grants_table.c.scope_id,
        },
        column_prefix="_col_",
    )
    _grant_mapped = True
