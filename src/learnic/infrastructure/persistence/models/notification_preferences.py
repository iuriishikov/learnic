"""SQLAlchemy table for :class:`NotificationPreferences`.

A flat boolean matrix — one column per ``(channel, category)``
pair — keeps reads single-row and writes a trivial upsert. The
shape is fixed by the :class:`NotificationCategory` enum, which
already lives at the entity boundary, so adding a new category
is a small migration plus an entity change rather than a schema
overhaul.

This table intentionally does NOT carry imperative mapping onto
the entity: the entity uses ``dict[NotificationCategory, bool]``
fields, which SQLAlchemy can't map to wide-column rows directly.
The gateway adapter does the dict ↔ row translation by hand.
"""

import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry


notification_preferences_table = sa.Table(
    "notification_preferences",
    mapper_registry.metadata,
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "push_invites",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
    ),
    sa.Column(
        "push_files",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
    ),
    sa.Column(
        "push_jobs",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
    ),
    sa.Column(
        "push_other",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
    ),
    sa.Column(
        "email_invites",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "email_files",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "email_jobs",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "email_other",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
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
    ),
)
