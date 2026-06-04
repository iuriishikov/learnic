import uuid

import pytest

from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.errors import BlogPostStatusTransitionError
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostTitle,
)
from learnic.entities.user.models import UserID


def _make() -> BlogPost:
    return BlogPost.create(
        title=BlogPostTitle("Hello"),
        slug=BlogPostSlug("hello-world"),
        created_by=UserID(uuid.uuid4()),
    )


class TestCreate:
    def test_initial_state_is_draft(self) -> None:
        post = _make()
        assert post.status is BlogPostStatus.DRAFT
        assert post.is_published is False
        assert post.published_at is None
        assert isinstance(post.oid, uuid.UUID)


class TestMutators:
    def test_rename(self) -> None:
        post = _make()
        post.rename(BlogPostTitle("New"))
        assert post.title.value == "New"

    def test_change_slug(self) -> None:
        post = _make()
        post.change_slug(BlogPostSlug("new-slug"))
        assert post.slug.value == "new-slug"


class TestPublishLifecycle:
    def test_publish_sets_status_and_timestamp(self) -> None:
        post = _make()
        post.publish()
        assert post.status is BlogPostStatus.PUBLISHED
        assert post.is_published is True
        assert post.published_at is not None

    def test_publish_when_already_published_raises(self) -> None:
        post = _make()
        post.publish()
        with pytest.raises(BlogPostStatusTransitionError) as exc:
            post.publish()
        assert exc.value.status == BlogPostStatus.PUBLISHED.value
        assert exc.value.operation == "publish"

    def test_unpublish_clears_timestamp(self) -> None:
        post = _make()
        post.publish()
        post.unpublish()
        assert post.status is BlogPostStatus.DRAFT
        assert post.published_at is None

    def test_unpublish_when_draft_raises(self) -> None:
        post = _make()
        with pytest.raises(BlogPostStatusTransitionError) as exc:
            post.unpublish()
        assert exc.value.status == BlogPostStatus.DRAFT.value
        assert exc.value.operation == "unpublish"
