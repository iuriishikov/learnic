from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.product_gift.constants import INVITE_TOKEN_HASH_LEN
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteTokenHash
from learnic.entities.user.constants import EMAIL_MAX_LEN
from learnic.entities.user.value_objects import Email
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


product_gifts_table = sa.Table(
    "product_gifts",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "recipient_id",
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
            GiftStatus,
            name="product_gift_status",
            values_callable=_enum_values,
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
        "uq_gift_product_recipient_active",
        "product_id",
        "recipient_id",
        unique=True,
        postgresql_where=sa.and_(
            sa.column("recipient_id").isnot(None),
            sa.column("status").notin_(
                [
                    GiftStatus.REVOKED.value,
                    GiftStatus.DECLINED.value,
                ],
            ),
        ),
    ),
    sa.Index(
        "uq_gift_product_email_pending",
        "product_id",
        "invited_email",
        unique=True,
        postgresql_where=sa.and_(
            sa.column("invited_email").isnot(None),
            sa.column("status") == GiftStatus.PENDING_INVITE.value,
        ),
    ),
    sa.Index(
        "ix_gift_recipient_id",
        "recipient_id",
    ),
)


_gift_mapped = False


def map_product_gift_table() -> None:
    """Apply imperative mapping for :class:`ProductGift`."""
    global _gift_mapped  # noqa: PLW0603
    if _gift_mapped:
        return
    mapper_registry.map_imperatively(
        ProductGift,
        product_gifts_table,
        properties={
            "oid": product_gifts_table.c.oid,
            "product_id": product_gifts_table.c.product_id,
            "recipient_id": product_gifts_table.c.recipient_id,
            "invited_email": composite(
                Email.of_optional,
                product_gifts_table.c.invited_email,
            ),
            "status": product_gifts_table.c.status,
            "invited_by": product_gifts_table.c.invited_by,
            "invite_token_hash": composite(
                InviteTokenHash.of_optional,
                product_gifts_table.c.invite_token_hash,
            ),
            "invite_expires_at": product_gifts_table.c.invite_expires_at,
            "created_at": product_gifts_table.c.created_at,
            "accepted_at": product_gifts_table.c.accepted_at,
            "declined_at": product_gifts_table.c.declined_at,
            "revoked_at": product_gifts_table.c.revoked_at,
        },
        column_prefix="_gift_",
    )
    _gift_mapped = True
