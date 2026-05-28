"""add email_sendings table for per-user email send rate limiting

Append-only audit log of user-initiated outbound emails. Backs the
cross-flow per-user send cap enforced by ``EmailSendRateLimiter``
(transaction-scoped advisory lock + windowed COUNT). The
``(actor_id, sent_at)`` index serves that COUNT. ``ip`` is stored for
abuse forensics only and is never used as a rate-limit key, so users
behind a shared VPN / NAT egress are not penalised for one another.

Revision ID: emlsnd0001
Revises: prodtouch0001
Create Date: 2026-05-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "emlsnd0001"
down_revision: Union[str, Sequence[str], None] = "prodtouch0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Self-contained snapshot of the column widths at this revision —
# mirrors EMAIL_MAX_LEN (user) and IP_MAX_LEN (email_sending). Inlined
# on purpose: migrations must not drift if the app constants change.
_RECIPIENT_MAX_LEN = 320
_IP_MAX_LEN = 45


def upgrade() -> None:
    op.create_table(
        "email_sendings",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "recipient",
            sa.String(length=_RECIPIENT_MAX_LEN),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=_IP_MAX_LEN), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_email_sendings_actor_sent_at",
        "email_sendings",
        ["actor_id", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_sendings_actor_sent_at",
        table_name="email_sendings",
    )
    op.drop_table("email_sendings")
