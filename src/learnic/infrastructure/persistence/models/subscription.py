"""SA Core tables for billing aggregates + imperative mapping."""

import sqlalchemy as sa

from learnic.entities.billing.constants import PLAN_CODE_MAX_LEN
from learnic.entities.billing.models import StorageQuotaBreach, Subscription
from learnic.infrastructure.persistence.models.registry import mapper_registry


subscriptions_table = sa.Table(
    "subscriptions",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "plan_code",
        sa.String(PLAN_CODE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "granted_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "granted_by",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Index(
        "ix_subscriptions_user_active",
        "user_id",
        "revoked_at",
        "expires_at",
    ),
)


storage_quota_breaches_table = sa.Table(
    "storage_quota_breaches",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    sa.Column(
        "plan_code",
        sa.String(PLAN_CODE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "detected_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("over_bytes", sa.BigInteger, nullable=False),
    sa.Column(
        "last_notified_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
)


_subscription_mapped = False
_storage_quota_breach_mapped = False


def map_subscription_table() -> None:
    """Apply imperative mapping from :class:`Subscription`."""
    global _subscription_mapped  # noqa: PLW0603
    if _subscription_mapped:
        return
    mapper_registry.map_imperatively(
        Subscription,
        subscriptions_table,
        properties={
            "oid": subscriptions_table.c.oid,
            "user_id": subscriptions_table.c.user_id,
            "plan_code": subscriptions_table.c.plan_code,
            "granted_at": subscriptions_table.c.granted_at,
            "expires_at": subscriptions_table.c.expires_at,
            "revoked_at": subscriptions_table.c.revoked_at,
            "granted_by": subscriptions_table.c.granted_by,
        },
        column_prefix="_col_",
    )
    _subscription_mapped = True


def map_storage_quota_breach_table() -> None:
    """Apply imperative mapping from :class:`StorageQuotaBreach`."""
    global _storage_quota_breach_mapped  # noqa: PLW0603
    if _storage_quota_breach_mapped:
        return
    mapper_registry.map_imperatively(
        StorageQuotaBreach,
        storage_quota_breaches_table,
        properties={
            "oid": storage_quota_breaches_table.c.oid,
            "user_id": storage_quota_breaches_table.c.user_id,
            "plan_code": storage_quota_breaches_table.c.plan_code,
            "detected_at": storage_quota_breaches_table.c.detected_at,
            "over_bytes": storage_quota_breaches_table.c.over_bytes,
            "last_notified_at": (
                storage_quota_breaches_table.c.last_notified_at
            ),
        },
        column_prefix="_col_",
    )
    _storage_quota_breach_mapped = True
