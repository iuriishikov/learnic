import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry

refresh_tokens_table = sa.Table(
    "refresh_tokens",
    mapper_registry.metadata,
    sa.Column("token_hash", sa.LargeBinary(32), primary_key=True),
    sa.Column("jti", sa.Uuid, nullable=False, unique=True),
    sa.Column("family_id", sa.Uuid, nullable=False),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "issued_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index(
        "ix_refresh_tokens_active_user",
        "user_id",
        postgresql_where=sa.text("revoked_at IS NULL"),
    ),
    sa.Index("ix_refresh_tokens_family", "family_id"),
)
