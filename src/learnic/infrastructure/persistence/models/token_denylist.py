import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry

token_denylist_table = sa.Table(
    "token_denylist",
    mapper_registry.metadata,
    sa.Column("jti", sa.Uuid, primary_key=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_token_denylist_expires", "expires_at"),
)
