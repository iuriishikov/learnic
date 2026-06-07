from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.blog_post.constants import (
    BLOG_POST_SLUG_MAX_LEN,
    BLOG_POST_SUBTITLE_MAX_LEN,
    BLOG_POST_TITLE_MAX_LEN,
    BLOG_POST_TOPIC_MAX_LEN,
)
from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostSubtitle,
    BlogPostTitle,
    BlogPostTopic,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


blog_posts_table = sa.Table(
    "blog_posts",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "title",
        sa.String(BLOG_POST_TITLE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "slug",
        sa.String(BLOG_POST_SLUG_MAX_LEN),
        nullable=False,
        unique=True,
    ),
    sa.Column(
        "status",
        sa.Enum(
            BlogPostStatus,
            name="blog_post_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=BlogPostStatus.DRAFT.value,
    ),
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
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.Column(
        "published_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    sa.Column(
        "cover_file_id",
        sa.Uuid,
        sa.ForeignKey(
            "files.oid",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_blog_posts_cover_file_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "subtitle",
        sa.String(BLOG_POST_SUBTITLE_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "topic",
        sa.String(BLOG_POST_TOPIC_MAX_LEN),
        nullable=True,
    ),
    # Public list ("newest published first") and admin filtered list
    # both sort by created_at after filtering on status.
    sa.Index(
        "ix_blog_posts_status_created_at",
        "status",
        "created_at",
    ),
)


_mapped = False


def map_blog_post_table() -> None:
    """Apply imperative mapping from :class:`BlogPost`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        BlogPost,
        blog_posts_table,
        properties={
            "oid": blog_posts_table.c.oid,
            "title": composite(
                BlogPostTitle,
                blog_posts_table.c.title,
            ),
            "slug": composite(
                BlogPostSlug,
                blog_posts_table.c.slug,
            ),
            "status": blog_posts_table.c.status,
            "created_by": blog_posts_table.c.created_by,
            "created_at": blog_posts_table.c.created_at,
            "updated_at": blog_posts_table.c.updated_at,
            "published_at": blog_posts_table.c.published_at,
            "cover_file_id": blog_posts_table.c.cover_file_id,
            # Nullable VO columns: SQLAlchemy 2.0 always instantiates the
            # composite on load, so a bare VO class would crash on a NULL.
            # The factory returns None instead (see CLAUDE.md rule 7).
            "subtitle": composite(
                lambda value: (
                    BlogPostSubtitle(value) if value is not None else None
                ),
                blog_posts_table.c.subtitle,
            ),
            "topic": composite(
                lambda value: (
                    BlogPostTopic(value) if value is not None else None
                ),
                blog_posts_table.c.topic,
            ),
        },
        column_prefix="_col_",
    )
    _mapped = True
