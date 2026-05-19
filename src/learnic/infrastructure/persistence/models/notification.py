"""SQLAlchemy mapping for :class:`Notification` (option B persistence).

The base ``notifications`` table holds shared columns and the
``kind`` discriminator. Each :class:`NotificationKind` has its own
``notification_<kind>`` subtype table with a composite
``(notification_id, kind)`` foreign key — that prevents
"comment-shaped" subtype rows from attaching to "invite-kind"
notifications at the database level.

Mapping is done imperatively to keep entities pure (no SA DSL on
domain models). The polymorphic ``details`` field is intentionally
NOT mapped — :class:`NotificationGatewayAlchemy` saves the right
subtype row alongside the parent, and :meth:`with_id` rebuilds
``details`` out-of-band by querying the matching subtype table.
"""

from enum import StrEnum

import sqlalchemy as sa

from learnic.entities.billing.constants import PLAN_CODE_MAX_LEN
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


notifications_table = sa.Table(
    "notifications",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "recipient_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "category",
        sa.Enum(
            NotificationCategory,
            name="notification_category",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "actor_id",
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
        "read_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    sa.UniqueConstraint(
        "oid",
        "kind",
        name="uq_notifications_oid_kind",
    ),
    sa.Index(
        "ix_notif_recipient_created",
        "recipient_id",
        sa.column("created_at").desc(),
    ),
    sa.Index(
        "ix_notif_recipient_category_created",
        "recipient_id",
        "category",
        sa.column("created_at").desc(),
    ),
    sa.Index(
        "ix_notif_recipient_unread",
        "recipient_id",
        postgresql_where=sa.column("read_at").is_(None),
    ),
)


notification_invite_sent_table = sa.Table(
    "notification_invite_sent",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
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
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_invite_sent_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.INVITE_SENT.value}'",
        name="ck_notif_invite_sent_kind",
    ),
)


notification_invite_accepted_table = sa.Table(
    "notification_invite_accepted",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
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
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "collaborator_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_invite_accepted_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.INVITE_ACCEPTED.value}'",
        name="ck_notif_invite_accepted_kind",
    ),
)


notification_invite_declined_table = sa.Table(
    "notification_invite_declined",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
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
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "decliner_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_invite_declined_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.INVITE_DECLINED.value}'",
        name="ck_notif_invite_declined_kind",
    ),
)


notification_new_login_table = sa.Table(
    "notification_new_login",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "session_id",
        sa.Uuid,
        nullable=False,
    ),
    sa.Column(
        "device_label",
        sa.String(128),
        nullable=True,
    ),
    sa.Column(
        "user_agent",
        sa.String(512),
        nullable=True,
    ),
    sa.Column(
        "ip_address",
        sa.String(64),
        nullable=True,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_new_login_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.NEW_LOGIN.value}'",
        name="ck_notif_new_login_kind",
    ),
)


notification_access_revoked_table = sa.Table(
    "notification_access_revoked",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
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
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "revoker_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_access_revoked_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.ACCESS_REVOKED.value}'",
        name="ck_notif_access_revoked_kind",
    ),
)


notification_storage_quota_warning_table = sa.Table(
    "notification_storage_quota_warning",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "plan_code",
        sa.String(PLAN_CODE_MAX_LEN),
        nullable=False,
    ),
    sa.Column("over_bytes", sa.BigInteger, nullable=False),
    sa.Column("plan_limit_bytes", sa.BigInteger, nullable=False),
    sa.Column(
        "grace_until",
        sa.DateTime(timezone=True),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_storage_quota_warning_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.STORAGE_QUOTA_WARNING.value}'",
        name="ck_notif_storage_quota_warning_kind",
    ),
)


notification_storage_quota_enforced_table = sa.Table(
    "notification_storage_quota_enforced",
    mapper_registry.metadata,
    sa.Column(
        "notification_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            NotificationKind,
            name="notification_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "plan_code",
        sa.String(PLAN_CODE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "deleted_files_count",
        sa.Integer,
        nullable=False,
    ),
    sa.Column("freed_bytes", sa.BigInteger, nullable=False),
    sa.ForeignKeyConstraint(
        ["notification_id", "kind"],
        ["notifications.oid", "notifications.kind"],
        ondelete="CASCADE",
        name="fk_notif_storage_quota_enforced_parent",
    ),
    sa.CheckConstraint(
        f"kind = '{NotificationKind.STORAGE_QUOTA_ENFORCED.value}'",
        name="ck_notif_storage_quota_enforced_kind",
    ),
)


_mapped = False


def map_notification_table() -> None:
    """Imperative mapping for :class:`Notification`.

    ``details`` is loaded by the gateway out-of-band — same pattern
    as ``ProductCollaboration.grants``. Subtype tables are pure SA
    Core writes / reads; they don't carry their own ORM mapping
    because the domain side already lives on
    :class:`NotificationDetails` subclasses (no shared base entity).
    """
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        Notification,
        notifications_table,
        properties={
            "oid": notifications_table.c.oid,
            "recipient_id": notifications_table.c.recipient_id,
            "kind": notifications_table.c.kind,
            "category": notifications_table.c.category,
            "actor_id": notifications_table.c.actor_id,
            "created_at": notifications_table.c.created_at,
            "read_at": notifications_table.c.read_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
