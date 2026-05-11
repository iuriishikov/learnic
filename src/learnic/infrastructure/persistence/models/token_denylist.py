import sqlalchemy as sa

from learnic.infrastructure.persistence.models.registry import mapper_registry

family_denylist_table = sa.Table(
    "family_denylist",
    mapper_registry.metadata,
    sa.Column("family_id", sa.Uuid, primary_key=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("ix_family_denylist_expires", "expires_at"),
)
