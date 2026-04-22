import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry

signup_sessions_table = sa.Table(
    "signup_sessions",
    mapper_registry.metadata,
    sa.Column("token_hash", sa.LargeBinary(32), primary_key=True),
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
    sa.Index("ix_signup_sessions_user", "user_id"),
)
