"""SQLAlchemy mapping for :class:`PushSubscription`.

One row per browser-device subscription. ``endpoint`` is the
natural key — push services issue it on subscribe and reuse it
on re-subscribe within the same browser-permission scope, so a
unique constraint keeps the upsert path correct.
"""

import sqlalchemy as sa

from learnic.entities.push_subscription.models import PushSubscription
from learnic.infrastructure.persistence.models.registry import mapper_registry


push_subscriptions_table = sa.Table(
    "push_subscriptions",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("endpoint", sa.Text, nullable=False),
    sa.Column("p256dh", sa.Text, nullable=False),
    sa.Column("auth", sa.Text, nullable=False),
    sa.Column("user_agent", sa.Text, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "last_seen_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    sa.Index(
        "ix_push_subscriptions_user_created",
        "user_id",
        sa.column("created_at").asc(),
    ),
)


_mapped = False


def map_push_subscription_table() -> None:
    """Imperative mapping; called once from :mod:`bootstrap`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        PushSubscription,
        push_subscriptions_table,
        properties={
            "oid": push_subscriptions_table.c.oid,
            "user_id": push_subscriptions_table.c.user_id,
            "endpoint": push_subscriptions_table.c.endpoint,
            "p256dh": push_subscriptions_table.c.p256dh,
            "auth": push_subscriptions_table.c.auth,
            "user_agent": push_subscriptions_table.c.user_agent,
            "created_at": push_subscriptions_table.c.created_at,
            "last_seen_at": push_subscriptions_table.c.last_seen_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
