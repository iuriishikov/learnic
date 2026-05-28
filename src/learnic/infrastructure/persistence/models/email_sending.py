"""SQLAlchemy imperative mapping for :class:`EmailSending`.

The ``email_sendings`` table is an append-only audit log of
user-initiated outbound emails and the backing store for the
per-user send rate limit. The ``(actor_id, sent_at)`` index serves
the windowed ``COUNT`` the limiter runs on every send.
"""

import sqlalchemy as sa

from learnic.entities.email_sending.constants import IP_MAX_LEN
from learnic.entities.email_sending.models import EmailSending
from learnic.entities.user.constants import EMAIL_MAX_LEN
from learnic.infrastructure.persistence.models.registry import (
    mapper_registry,
)

email_sendings_table = sa.Table(
    "email_sendings",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "actor_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "recipient",
        sa.String(EMAIL_MAX_LEN),
        nullable=False,
    ),
    sa.Column("ip", sa.String(IP_MAX_LEN), nullable=True),
    sa.Column(
        "sent_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index(
        "ix_email_sendings_actor_sent_at",
        "actor_id",
        "sent_at",
    ),
)


_mapped = False


def map_email_sending_table() -> None:
    """Imperatively map :class:`EmailSending` to ``email_sendings``."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        EmailSending,
        email_sendings_table,
        properties={
            "oid": email_sendings_table.c.oid,
            "actor_id": email_sendings_table.c.actor_id,
            "recipient": email_sendings_table.c.recipient,
            "ip": email_sendings_table.c.ip,
            "sent_at": email_sendings_table.c.sent_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
