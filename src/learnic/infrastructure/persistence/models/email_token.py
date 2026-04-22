import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry

email_tokens_table = sa.Table(
    "email_tokens",
    mapper_registry.metadata,
    sa.Column("token_hash", sa.LargeBinary(32), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("purpose", sa.String(16), nullable=False),
    sa.Column(
        "issued_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index(
        "ix_email_tokens_active",
        "user_id",
        "purpose",
        postgresql_where=sa.text("consumed_at IS NULL"),
    ),
)
