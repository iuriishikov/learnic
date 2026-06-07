import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.blog_post.change_slug import (
    ChangeBlogPostSlugCommand,
    ChangeBlogPostSlugCommandHandler,
)
from learnic.application.commands.blog_post.cover.remove import (
    RemoveBlogPostCoverCommand,
    RemoveBlogPostCoverCommandHandler,
)
from learnic.application.commands.blog_post.cover.set import (
    SetBlogPostCoverCommand,
    SetBlogPostCoverCommandHandler,
)
from learnic.application.commands.blog_post.create import (
    CreateBlogPostCommand,
    CreateBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.delete import (
    DeleteBlogPostCommand,
    DeleteBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.edit_meta import (
    EditBlogPostMetaCommand,
    EditBlogPostMetaCommandHandler,
)
from learnic.application.commands.blog_post.publish import (
    PublishBlogPostCommand,
    PublishBlogPostCommandHandler,
)
from learnic.application.commands.blog_post_block.add_html import (
    AddBlogHtmlBlockCommand,
    AddBlogHtmlBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.add_image import (
    AddBlogImageBlockCommand,
    AddBlogImageBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.delete import (
    DeleteBlogPostBlockCommand,
    DeleteBlogPostBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.reorder import (
    ReorderBlogPostBlocksCommand,
    ReorderBlogPostBlocksCommandHandler,
)
from learnic.application.commands.blog_post_block.update_html import (
    UpdateBlogHtmlBlockCommand,
    UpdateBlogHtmlBlockCommandHandler,
)
from learnic.application.common.errors import (
    BlogPostSlugAlreadyTakenError,
    EntityNotFoundError,
    InvalidReorderError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.entities.blog_post.errors import BlogPostStatusTransitionError
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post.value_objects import (
    BlogPostSubtitle,
    BlogPostTopic,
)
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.file.ids import FileID
from learnic.entities.blog_post_block.models import (
    BlogHtmlBlock,
    BlogImageBlock,
    BlogVideoBlock,
)
from learnic.entities.common.limits import BLOG_POST_BLOCK_LIMIT
from learnic.entities.user.models import UserID
from tests.unit.application.blog_post.conftest import FakeUpload


class TestCreate:
    async def test_creates_when_slug_free(
        self,
        fake_transaction: AsyncMock,
        fake_entity_saver: MagicMock,
        fake_blog_post_gateway: AsyncMock,
        actor_id: UserID,
    ) -> None:
        handler = CreateBlogPostCommandHandler(
            fake_transaction, fake_entity_saver, fake_blog_post_gateway,
        )
        oid = await handler.run(
            CreateBlogPostCommand(
                actor_id=actor_id, title="Hi", slug="hi-there",
            ),
        )
        assert isinstance(oid, uuid.UUID)
        fake_entity_saver.add_one.assert_called_once()
        fake_transaction.commit.assert_called_once()

    async def test_rejects_taken_slug(
        self,
        fake_transaction: AsyncMock,
        fake_entity_saver: MagicMock,
        fake_blog_post_gateway: AsyncMock,
        actor_id: UserID,
    ) -> None:
        fake_blog_post_gateway.slug_exists.return_value = True
        handler = CreateBlogPostCommandHandler(
            fake_transaction, fake_entity_saver, fake_blog_post_gateway,
        )
        with pytest.raises(BlogPostSlugAlreadyTakenError):
            await handler.run(
                CreateBlogPostCommand(
                    actor_id=actor_id, title="Hi", slug="taken-slug",
                ),
            )
        fake_entity_saver.add_one.assert_not_called()
        fake_transaction.commit.assert_not_called()


class TestChangeSlug:
    async def test_unchanged_slug_skips_uniqueness_check(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        draft_post: BlogPost,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = ChangeBlogPostSlugCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        await handler.run(
            ChangeBlogPostSlugCommand(
                post_id=BlogPostID(draft_post.oid),
                slug=draft_post.slug.value,
            ),
        )
        fake_blog_post_gateway.slug_exists.assert_not_called()
        fake_transaction.commit.assert_called_once()

    async def test_new_taken_slug_rejected(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        draft_post: BlogPost,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_blog_post_gateway.slug_exists.return_value = True
        handler = ChangeBlogPostSlugCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        with pytest.raises(BlogPostSlugAlreadyTakenError):
            await handler.run(
                ChangeBlogPostSlugCommand(
                    post_id=BlogPostID(draft_post.oid), slug="other-slug",
                ),
            )


class TestPublish:
    async def test_publish_missing_post_raises(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = None
        handler = PublishBlogPostCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        with pytest.raises(EntityNotFoundError):
            await handler.run(
                PublishBlogPostCommand(post_id=BlogPostID(uuid.uuid4())),
            )

    async def test_publish_twice_raises_transition(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        draft_post: BlogPost,
    ) -> None:
        draft_post.publish()
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = PublishBlogPostCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        with pytest.raises(BlogPostStatusTransitionError):
            await handler.run(
                PublishBlogPostCommand(post_id=BlogPostID(draft_post.oid)),
            )


class TestEditMeta:
    async def test_sets_subtitle_and_role(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        draft_post: BlogPost,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = EditBlogPostMetaCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        await handler.run(
            EditBlogPostMetaCommand(
                post_id=BlogPostID(draft_post.oid),
                subtitle="A short deck",
                topic="Design",
            ),
        )
        assert draft_post.subtitle is not None
        assert draft_post.subtitle.value == "A short deck"
        assert draft_post.topic is not None
        assert draft_post.topic.value == "Design"
        fake_transaction.commit.assert_awaited_once()

    @pytest.mark.parametrize("value", [None, "", "   "])
    async def test_blank_clears_fields(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        draft_post: BlogPost,
        value: str | None,
    ) -> None:
        draft_post.edit_meta(
            BlogPostSubtitle("old"),
            BlogPostTopic("Design"),
        )
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = EditBlogPostMetaCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        await handler.run(
            EditBlogPostMetaCommand(
                post_id=BlogPostID(draft_post.oid),
                subtitle=value,
                topic=value,
            ),
        )
        assert draft_post.subtitle is None
        assert draft_post.topic is None

    async def test_missing_post_raises(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = None
        handler = EditBlogPostMetaCommandHandler(
            fake_transaction, fake_blog_post_gateway,
        )
        with pytest.raises(EntityNotFoundError):
            await handler.run(
                EditBlogPostMetaCommand(
                    post_id=BlogPostID(uuid.uuid4()),
                    subtitle="x",
                    topic="y",
                ),
            )


class TestAddHtmlBlock:
    async def test_appends_at_next_position(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_html_sanitizer: MagicMock,
        draft_post: BlogPost,
        html_block: BlogHtmlBlock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_block_gateway.list_for_post.return_value = [html_block]
        handler = AddBlogHtmlBlockCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_html_sanitizer,
        )
        await handler.run(
            AddBlogHtmlBlockCommand(
                post_id=BlogPostID(draft_post.oid), html="<p>new</p>",
            ),
        )
        fake_block_gateway.lock_for_post.assert_called_once()
        added = fake_block_gateway.add_html.call_args.args[0]
        assert added.position == 1  # after the one existing block
        fake_transaction.commit.assert_called_once()

    async def test_missing_post_raises(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_html_sanitizer: MagicMock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = None
        handler = AddBlogHtmlBlockCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_html_sanitizer,
        )
        with pytest.raises(EntityNotFoundError):
            await handler.run(
                AddBlogHtmlBlockCommand(
                    post_id=BlogPostID(uuid.uuid4()), html="<p>x</p>",
                ),
            )

    async def test_block_cap_enforced(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_html_sanitizer: MagicMock,
        draft_post: BlogPost,
        html_block: BlogHtmlBlock,
    ) -> None:
        from learnic.entities.common.limits import ResourceLimitReachedError

        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_block_gateway.list_for_post.return_value = [
            html_block,
        ] * BLOG_POST_BLOCK_LIMIT.max_count
        handler = AddBlogHtmlBlockCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_html_sanitizer,
        )
        with pytest.raises(ResourceLimitReachedError):
            await handler.run(
                AddBlogHtmlBlockCommand(
                    post_id=BlogPostID(draft_post.oid), html="<p>x</p>",
                ),
            )
        fake_block_gateway.add_html.assert_not_called()


class TestAddImageBlock:
    async def test_rejects_non_image_before_upload(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
        actor_id: UserID,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = AddBlogImageBlockCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_file_uploads,
        )
        with pytest.raises(WrongFileContentTypeError):
            await handler.run(
                AddBlogImageBlockCommand(
                    actor_id=actor_id,
                    post_id=BlogPostID(draft_post.oid),
                    upload=FakeUpload("application/pdf"),
                ),
            )
        fake_file_uploads.upload_stream.assert_not_called()
        fake_block_gateway.add_image.assert_not_called()

    async def test_uploads_and_appends_image(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
        actor_id: UserID,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = AddBlogImageBlockCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_file_uploads,
        )
        await handler.run(
            AddBlogImageBlockCommand(
                actor_id=actor_id,
                post_id=BlogPostID(draft_post.oid),
                upload=FakeUpload("image/png"),
                caption="cap",
            ),
        )
        fake_file_uploads.upload_stream.assert_called_once()
        fake_block_gateway.add_image.assert_called_once()
        fake_transaction.commit.assert_called_once()


class TestUpdateHtmlBlock:
    async def test_wrong_block_type_rejected(
        self,
        fake_transaction: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_html_sanitizer: MagicMock,
        image_block: BlogImageBlock,
    ) -> None:
        fake_block_gateway.with_id.return_value = image_block
        handler = UpdateBlogHtmlBlockCommandHandler(
            fake_transaction, fake_block_gateway, fake_html_sanitizer,
        )
        with pytest.raises(WrongBlockTypeError):
            await handler.run(
                UpdateBlogHtmlBlockCommand(
                    block_id=BlogPostBlockID(image_block.oid), html="<p>x</p>",
                ),
            )


class TestDeleteBlock:
    async def test_image_block_reclaims_file(
        self,
        fake_transaction: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        image_block: BlogImageBlock,
    ) -> None:
        fake_block_gateway.with_id.return_value = image_block
        handler = DeleteBlogPostBlockCommandHandler(
            fake_transaction, fake_block_gateway, fake_file_uploads,
        )
        await handler.run(
            DeleteBlogPostBlockCommand(block_id=BlogPostBlockID(image_block.oid)),
        )
        fake_block_gateway.delete.assert_called_once()
        fake_file_uploads.soft_delete_previous.assert_called_once_with(
            image_block.file_id,
        )

    async def test_html_block_has_no_file_cleanup(
        self,
        fake_transaction: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        html_block: BlogHtmlBlock,
    ) -> None:
        fake_block_gateway.with_id.return_value = html_block
        handler = DeleteBlogPostBlockCommandHandler(
            fake_transaction, fake_block_gateway, fake_file_uploads,
        )
        await handler.run(
            DeleteBlogPostBlockCommand(block_id=BlogPostBlockID(html_block.oid)),
        )
        fake_block_gateway.delete.assert_called_once()
        fake_file_uploads.soft_delete_previous.assert_not_called()


class TestReorder:
    async def test_valid_permutation(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        draft_post: BlogPost,
        html_block: BlogHtmlBlock,
        image_block: BlogImageBlock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_block_gateway.list_for_post.return_value = [html_block, image_block]
        handler = ReorderBlogPostBlocksCommandHandler(
            fake_transaction, fake_blog_post_gateway, fake_block_gateway,
        )
        await handler.run(
            ReorderBlogPostBlocksCommand(
                post_id=BlogPostID(draft_post.oid),
                ordered_ids=[
                    BlogPostBlockID(image_block.oid),
                    BlogPostBlockID(html_block.oid),
                ],
            ),
        )
        fake_block_gateway.reorder.assert_called_once()

    async def test_mismatched_ids_rejected(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        draft_post: BlogPost,
        html_block: BlogHtmlBlock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_block_gateway.list_for_post.return_value = [html_block]
        handler = ReorderBlogPostBlocksCommandHandler(
            fake_transaction, fake_blog_post_gateway, fake_block_gateway,
        )
        with pytest.raises(InvalidReorderError):
            await handler.run(
                ReorderBlogPostBlocksCommand(
                    post_id=BlogPostID(draft_post.oid),
                    ordered_ids=[BlogPostBlockID(uuid.uuid4())],
                ),
            )
        fake_block_gateway.reorder.assert_not_called()


class TestListOrdering:
    async def test_public_index_orders_by_published_date(self) -> None:
        from learnic.application.common.pagination import Pagination
        from learnic.application.common.persistence.blog_post import (
            BlogPostOrder,
        )
        from learnic.application.queries.blog_post.list_published import (
            ListPublishedBlogPostsQuery,
            ListPublishedBlogPostsQueryHandler,
        )

        reader = AsyncMock()
        reader.list = AsyncMock(return_value=[])
        reader.count = AsyncMock(return_value=0)
        handler = ListPublishedBlogPostsQueryHandler(reader)
        await handler.run(
            ListPublishedBlogPostsQuery(
                pagination=Pagination(limit=20, offset=0),
            ),
        )
        assert (
            reader.list.call_args.kwargs["order"]
            is BlogPostOrder.PUBLISHED_DESC
        )

    async def test_admin_list_uses_default_created_order(self) -> None:
        from learnic.application.common.pagination import Pagination
        from learnic.application.queries.blog_post.list import (
            ListBlogPostsQuery,
            ListBlogPostsQueryHandler,
        )

        reader = AsyncMock()
        reader.list = AsyncMock(return_value=[])
        reader.count = AsyncMock(return_value=0)
        handler = ListBlogPostsQueryHandler(reader)
        await handler.run(
            ListBlogPostsQuery(pagination=Pagination(limit=20, offset=0)),
        )
        # Admin handler does not pass an explicit order → reader's
        # default (CREATED_DESC) applies.
        assert "order" not in reader.list.call_args.kwargs


class TestDeletePost:
    async def test_collects_media_files_and_cascades(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_block_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
        html_block: BlogHtmlBlock,
        image_block: BlogImageBlock,
        video_block: BlogVideoBlock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        fake_block_gateway.list_for_post.return_value = [
            html_block, image_block, video_block,
        ]
        handler = DeleteBlogPostCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_block_gateway,
            fake_file_uploads,
        )
        await handler.run(
            DeleteBlogPostCommand(post_id=BlogPostID(draft_post.oid)),
        )
        fake_blog_post_gateway.delete.assert_called_once()
        # only image + video carry files; html does not
        assert fake_file_uploads.soft_delete_previous.await_count == 2
        fake_transaction.commit.assert_called_once()


class TestCover:
    async def test_set_uploads_attaches_and_commits(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
        actor_id: UserID,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = SetBlogPostCoverCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_file_uploads,
        )

        new_file_id = await handler.run(
            SetBlogPostCoverCommand(
                actor_id=actor_id,
                post_id=BlogPostID(draft_post.oid),
                upload=FakeUpload("image/png"),
            ),
        )

        assert draft_post.cover_file_id == new_file_id
        fake_file_uploads.upload_stream.assert_awaited_once()
        # No previous cover -> the soft-delete is a no-op on None.
        fake_file_uploads.soft_delete_previous.assert_awaited_once_with(None)
        fake_transaction.commit.assert_awaited_once()

    async def test_set_replaces_soft_deletes_previous(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
        actor_id: UserID,
    ) -> None:
        previous = FileID(uuid.uuid4())
        draft_post.cover_file_id = previous
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = SetBlogPostCoverCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_file_uploads,
        )

        new_file_id = await handler.run(
            SetBlogPostCoverCommand(
                actor_id=actor_id,
                post_id=BlogPostID(draft_post.oid),
                upload=FakeUpload("image/jpeg"),
            ),
        )

        assert draft_post.cover_file_id == new_file_id
        fake_file_uploads.soft_delete_previous.assert_awaited_once_with(
            previous,
        )
        fake_transaction.commit.assert_awaited_once()

    async def test_set_missing_post_raises(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        actor_id: UserID,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = None
        handler = SetBlogPostCoverCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_file_uploads,
        )

        with pytest.raises(EntityNotFoundError):
            await handler.run(
                SetBlogPostCoverCommand(
                    actor_id=actor_id,
                    post_id=BlogPostID(uuid.uuid4()),
                    upload=FakeUpload("image/png"),
                ),
            )
        fake_file_uploads.upload_stream.assert_not_awaited()
        fake_transaction.commit.assert_not_awaited()

    async def test_remove_detaches_and_soft_deletes(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
        draft_post: BlogPost,
    ) -> None:
        previous = FileID(uuid.uuid4())
        draft_post.cover_file_id = previous
        fake_blog_post_gateway.with_id.return_value = draft_post
        handler = RemoveBlogPostCoverCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_file_uploads,
        )

        await handler.run(
            RemoveBlogPostCoverCommand(post_id=BlogPostID(draft_post.oid)),
        )

        assert draft_post.cover_file_id is None
        fake_file_uploads.soft_delete_previous.assert_awaited_once_with(
            previous,
        )
        fake_transaction.commit.assert_awaited_once()

    async def test_remove_missing_post_raises(
        self,
        fake_transaction: AsyncMock,
        fake_blog_post_gateway: AsyncMock,
        fake_file_uploads: MagicMock,
    ) -> None:
        fake_blog_post_gateway.with_id.return_value = None
        handler = RemoveBlogPostCoverCommandHandler(
            fake_transaction,
            fake_blog_post_gateway,
            fake_file_uploads,
        )

        with pytest.raises(EntityNotFoundError):
            await handler.run(
                RemoveBlogPostCoverCommand(post_id=BlogPostID(uuid.uuid4())),
            )
        fake_file_uploads.soft_delete_previous.assert_not_awaited()
        fake_transaction.commit.assert_not_awaited()
