import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostTitle,
)
from learnic.entities.blog_post_block.models import (
    BlogHtmlBlock,
    BlogImageBlock,
    BlogVideoBlock,
)
from learnic.entities.blog_post_block.value_objects import BlogHtmlContent
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.user.models import UserID


class FakeUpload:
    """Minimal ``IncomingUpload`` stand-in for handler tests."""

    def __init__(self, content_type: str, size: int = 1024) -> None:
        self._content_type: Final = content_type
        self._size: Final = size

    @property
    def size(self) -> int:
        return self._size

    @property
    def content_type(self) -> str:
        return self._content_type

    async def stream(self, chunk_size: int) -> AsyncIterator[bytes]:  # noqa: ARG002
        yield b""


@pytest.fixture
def actor_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_html_sanitizer() -> MagicMock:
    sanitizer = MagicMock()
    sanitizer.sanitize = MagicMock(side_effect=lambda raw: raw)
    return sanitizer


@pytest.fixture
def fake_blog_post_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    gw.slug_exists = AsyncMock(return_value=False)
    gw.delete = AsyncMock()
    return gw


@pytest.fixture
def fake_block_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    gw.list_for_post = AsyncMock(return_value=[])
    gw.lock_for_post = AsyncMock()
    gw.add_html = AsyncMock()
    gw.update_html = AsyncMock()
    gw.add_image = AsyncMock()
    gw.update_image = AsyncMock()
    gw.add_video = AsyncMock()
    gw.update_video = AsyncMock()
    gw.delete = AsyncMock()
    gw.reorder = AsyncMock()
    return gw


@pytest.fixture
def fake_file_uploads() -> MagicMock:
    def _build_file(upload: object, uploaded_by: UserID) -> File:
        return File(
            oid=FileID(uuid.uuid4()),
            storage_name=StorageName(str(uuid.uuid4())),
            bucket=StorageBucket("test-bucket"),
            content_type=ContentType(upload.content_type),  # type: ignore[attr-defined]
            size_bytes=FileSize(upload.size),  # type: ignore[attr-defined]
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

    svc = MagicMock()
    svc.upload_stream = AsyncMock(side_effect=_build_file)
    svc.soft_delete_previous = AsyncMock()
    svc.previous_file_size = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def draft_post() -> BlogPost:
    return BlogPost.create(
        title=BlogPostTitle("Hello"),
        slug=BlogPostSlug("hello-world"),
        created_by=UserID(uuid.uuid4()),
    )


@pytest.fixture
def html_block(draft_post: BlogPost) -> BlogHtmlBlock:
    return BlogHtmlBlock.create(
        post_id=BlogPostID(draft_post.oid),
        html=BlogHtmlContent("<p>existing</p>"),
        position=0,
    )


@pytest.fixture
def image_block(draft_post: BlogPost) -> BlogImageBlock:
    return BlogImageBlock.create(
        post_id=BlogPostID(draft_post.oid),
        file_id=FileID(uuid.uuid4()),
        position=0,
    )


@pytest.fixture
def video_block(draft_post: BlogPost) -> BlogVideoBlock:
    return BlogVideoBlock.create(
        post_id=BlogPostID(draft_post.oid),
        file_id=FileID(uuid.uuid4()),
        position=1,
    )
