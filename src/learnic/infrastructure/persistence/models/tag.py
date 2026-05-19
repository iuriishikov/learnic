import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.tag.constants import (
    TAG_COLOR_MAX_LEN,
    TAG_NAME_MAX_LEN,
)
from learnic.entities.tag.models import Tag
from learnic.entities.tag.value_objects import TagColor, TagName, TagSlug
from learnic.infrastructure.persistence.models.registry import mapper_registry

tags_table = sa.Table(
    "tags",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column("name", sa.String(TAG_NAME_MAX_LEN), nullable=False),
    sa.Column("slug", sa.String(TAG_NAME_MAX_LEN), nullable=False),
    sa.Column("color", sa.String(TAG_COLOR_MAX_LEN), nullable=False),
    sa.Column(
        "created_by",
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
    sa.UniqueConstraint("slug", name="uq_tags_slug"),
    # Powers the autocomplete ``LIKE :q || '%'`` lookup; the
    # case-insensitive collation is irrelevant because the slug
    # is already lower-cased at insert time.
    sa.Index("ix_tags_slug", "slug"),
)


product_tags_table = sa.Table(
    "product_tags",
    mapper_registry.metadata,
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "tag_id",
        sa.Uuid,
        sa.ForeignKey("tags.oid", ondelete="RESTRICT"),
        primary_key=True,
    ),
    # 0-based author-defined order; rewritten in full on every
    # ``PUT /products/{id}/tags``.
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_product_tags_tag_id", "tag_id"),
)


_tag_mapped = False


def map_tag_table() -> None:
    """Apply imperative mapping from :class:`Tag` to ``tags_table``."""
    global _tag_mapped  # noqa: PLW0603
    if _tag_mapped:
        return
    mapper_registry.map_imperatively(
        Tag,
        tags_table,
        properties={
            "oid": tags_table.c.oid,
            "name": composite(TagName, tags_table.c.name),
            "slug": composite(TagSlug, tags_table.c.slug),
            "color": composite(TagColor, tags_table.c.color),
            "created_by": tags_table.c.created_by,
            "created_at": tags_table.c.created_at,
        },
        column_prefix="_col_",
    )
    _tag_mapped = True
