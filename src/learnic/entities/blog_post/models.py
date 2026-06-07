import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.errors import BlogPostStatusTransitionError
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostSubtitle,
    BlogPostTitle,
    BlogPostTopic,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
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
    cover_file_id: FileID | None = None
    subtitle: BlogPostSubtitle | None = None
    topic: BlogPostTopic | None = None

    @property
    def is_published(self) -> bool:
        return self.status is BlogPostStatus.PUBLISHED

    def edit_meta(
        self,
        subtitle: BlogPostSubtitle | None,
        topic: BlogPostTopic | None,
    ) -> None:
        """Replace the post's editorial metadata.

        Both fields are set wholesale (``None`` clears): the ``subtitle``
        (short description under the title) and the ``topic`` (category
        label above the title). The author's name and avatar are not
        stored here — they are resolved from ``created_by`` on the read
        side.
        """
        self.subtitle = subtitle
        self.topic = topic

    def rename(self, new_title: BlogPostTitle) -> None:
        self.title = new_title

    def change_slug(self, new_slug: BlogPostSlug) -> None:
        self.slug = new_slug

    def set_cover(self, file_id: FileID) -> FileID | None:
        """Attach ``file_id`` as cover, returning the previous one (if any)."""
        previous = self.cover_file_id
        self.cover_file_id = file_id
        return previous

    def remove_cover(self) -> FileID | None:
        """Detach the cover, returning the previous file id (if any)."""
        previous = self.cover_file_id
        self.cover_file_id = None
        return previous

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
