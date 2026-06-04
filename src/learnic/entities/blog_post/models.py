import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.errors import BlogPostStatusTransitionError
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostTitle,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.models import UserID


@dataclass
class BlogPost(BaseEntity[BlogPostID]):
    """A blog post authored by a platform administrator.

    The post is the aggregate root; its body lives in an ordered list
    of blocks (image / html / video) modelled by
    :mod:`learnic.entities.blog_post_block`. A post is created in
    ``DRAFT`` status (admin-only visibility) and toggled to
    ``PUBLISHED`` (public visibility) via :meth:`publish`.

    ``created_by`` is the administrator who created the post; it is
    nullable so the post survives that admin's account deletion
    (mirrors the ``ON DELETE SET NULL`` FK at the persistence
    boundary). ``published_at`` is the instant of the most recent
    publish and is cleared when the post returns to draft.
    """

    title: BlogPostTitle
    slug: BlogPostSlug
    status: BlogPostStatus
    created_by: UserID | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    @property
    def is_published(self) -> bool:
        return self.status is BlogPostStatus.PUBLISHED

    def rename(self, new_title: BlogPostTitle) -> None:
        self.title = new_title

    def change_slug(self, new_slug: BlogPostSlug) -> None:
        self.slug = new_slug

    def publish(self) -> None:
        """Move the post to ``PUBLISHED`` and stamp ``published_at``.

        Raises:
            BlogPostStatusTransitionError: The post is already
                published — publishing is only valid from ``DRAFT``.
        """
        if self.status is BlogPostStatus.PUBLISHED:
            raise BlogPostStatusTransitionError(
                status=self.status.value,
                operation="publish",
            )
        self.status = BlogPostStatus.PUBLISHED
        self.published_at = datetime.now(timezone.utc)

    def unpublish(self) -> None:
        """Return the post to ``DRAFT`` and clear ``published_at``.

        Raises:
            BlogPostStatusTransitionError: The post is already a draft —
                unpublishing is only valid from ``PUBLISHED``.
        """
        if self.status is BlogPostStatus.DRAFT:
            raise BlogPostStatusTransitionError(
                status=self.status.value,
                operation="unpublish",
            )
        self.status = BlogPostStatus.DRAFT
        self.published_at = None

    @classmethod
    def create(
        cls,
        title: BlogPostTitle,
        slug: BlogPostSlug,
        created_by: UserID,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=BlogPostID(uuid.uuid4()),
            title=title,
            slug=slug,
            status=BlogPostStatus.DRAFT,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            published_at=None,
        )
