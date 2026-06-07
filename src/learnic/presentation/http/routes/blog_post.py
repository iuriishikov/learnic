"""Blog API — admin-authored posts with image / html / video blocks.

Two routers share one module:

* ``public_router`` (``/blog/posts``) — unauthenticated reads of
  **published** posts (paginated index + fetch-by-slug with blocks).
* ``admin_router`` (``/admin/blog/posts``) — every write plus reads in
  any status, all gated by the platform-admin flag via
  :class:`AdminAuthenticator`. Blocks are sub-resources nested under
  ``/{post_id}/blocks`` per the REST-hierarchy rule.

Media (image / video) blocks accept ``multipart/form-data`` uploads;
the bytes land in object storage via the shared file pipeline and the
read views carry short-lived presigned URLs.
"""

from datetime import datetime
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import (
    Depends,
    File,
    Form,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Discriminator, Field

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
from learnic.application.commands.blog_post.rename import (
    RenameBlogPostCommand,
    RenameBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.unpublish import (
    UnpublishBlogPostCommand,
    UnpublishBlogPostCommandHandler,
)
from learnic.application.commands.blog_post_block.add_html import (
    AddBlogHtmlBlockCommand,
    AddBlogHtmlBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.add_image import (
    AddBlogImageBlockCommand,
    AddBlogImageBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.add_video import (
    AddBlogVideoBlockCommand,
    AddBlogVideoBlockCommandHandler,
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
from learnic.application.commands.blog_post_block.update_image import (
    UpdateBlogImageBlockCommand,
    UpdateBlogImageBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.update_video import (
    UpdateBlogVideoBlockCommand,
    UpdateBlogVideoBlockCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidReorderError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.common.persistence.blog_post import (
    BlogHtmlBlockView,
    BlogImageBlockView,
    BlogPostBlockView,
    BlogPostSummaryView,
    BlogPostView,
    BlogVideoBlockView,
)
from learnic.application.queries.blog_post.get import (
    GetBlogPostQuery,
    GetBlogPostQueryHandler,
)
from learnic.application.queries.blog_post.get_block import (
    GetBlogPostBlockQuery,
    GetBlogPostBlockQueryHandler,
)
from learnic.application.queries.blog_post.get_by_slug import (
    GetPublishedBlogPostBySlugQuery,
    GetPublishedBlogPostBySlugQueryHandler,
)
from learnic.application.queries.blog_post.list import (
    ListBlogPostsQuery,
    ListBlogPostsQueryHandler,
)
from learnic.application.queries.blog_post.list_published import (
    ListPublishedBlogPostsQuery,
    ListPublishedBlogPostsQueryHandler,
)
from learnic.entities.blog_post.constants import (
    BLOG_POST_SLUG_MAX_LEN,
    BLOG_POST_SLUG_MIN_LEN,
    BLOG_POST_SUBTITLE_MAX_LEN,
    BLOG_POST_TITLE_MAX_LEN,
    BLOG_POST_TOPIC_MAX_LEN,
)
from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.errors import BlogPostStatusTransitionError
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.constants import (
    BLOG_BLOCK_CAPTION_MAX_LEN,
    BLOG_HTML_BLOCK_MAX_LEN,
)
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.common.limits import ResourceLimitReachedError
from learnic.presentation.http.common.admin_deps import AdminAuthenticator
from learnic.presentation.http.common.auth_deps import access_cookie_scheme
from learnic.presentation.http.common.errors.rules import (
    ADMIN_MAP,
    BLOG_ADMIN_FIELD_MAP,
    BLOG_ADMIN_SLUG_MAP,
    BLOG_POST_STATUS_RULE,
    ENTITY_NOT_FOUND_RULE,
    INVALID_REORDER_RULE,
    RESOURCE_LIMIT_RULE,
    WRONG_BLOCK_TYPE_RULE,
    WRONG_FILE_CONTENT_TYPE_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import FileSchema
from learnic.presentation.http.common.upload_limits import (
    BLOG_COVER_MAX_BYTES,
    BLOG_IMAGE_BLOCK_MAX_BYTES,
    BLOG_VIDEO_BLOCK_MAX_BYTES,
)
from learnic.presentation.http.common.uploads import open_upload

public_router = ErrorAwareRouter(
    prefix="/blog/posts",
    tags=["BlogPosts"],
    route_class=DishkaErrorAwareRoute,
)
admin_router = ErrorAwareRouter(
    prefix="/admin/blog/posts",
    tags=["BlogPosts"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_POST_ID_PATH: Final = Path(
    description="Blog post UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_BLOCK_ID_PATH: Final = Path(
    description="Blog-post block UUID.",
    examples=["c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"],
)
_SLUG_PATH: Final = Path(
    description="URL-friendly post slug (lowercase, hyphen-separated).",
    examples=["my-first-post"],
)
_TITLE_FIELD: Final = Field(
    description=(
        "Post title shown in the index and as the page heading. "
        f"1–{BLOG_POST_TITLE_MAX_LEN} chars (`BLOG_POST_TITLE_MAX_LEN`)."
    ),
    min_length=1,
    max_length=BLOG_POST_TITLE_MAX_LEN,
    examples=["Announcing our new note platform"],
)
_SLUG_FIELD: Final = Field(
    description=(
        "URL-friendly identifier: lowercase alphanumerics joined by "
        "single hyphens (`my-first-post`). "
        f"{BLOG_POST_SLUG_MIN_LEN}–{BLOG_POST_SLUG_MAX_LEN} chars "
        "(`BLOG_POST_SLUG_MIN_LEN` / `BLOG_POST_SLUG_MAX_LEN`); must "
        "match `^[a-z0-9]+(?:-[a-z0-9]+)*$` and be globally unique."
    ),
    min_length=BLOG_POST_SLUG_MIN_LEN,
    max_length=BLOG_POST_SLUG_MAX_LEN,
    examples=["my-first-post"],
)
_SUBTITLE_FIELD: Final = Field(
    default=None,
    description=(
        "Optional deck / standfirst shown under the title on the public "
        f"post page. Up to {BLOG_POST_SUBTITLE_MAX_LEN} chars "
        "(`BLOG_POST_SUBTITLE_MAX_LEN`); `null` or blank clears it."
    ),
    max_length=BLOG_POST_SUBTITLE_MAX_LEN,
    examples=["The rise of RESTful APIs, and the tools that tame them."],
)
_TOPIC_FIELD: Final = Field(
    default=None,
    description=(
        "Optional topic / category label shown above the title on the "
        f"public post page. Up to {BLOG_POST_TOPIC_MAX_LEN} chars "
        "(`BLOG_POST_TOPIC_MAX_LEN`); `null` or blank clears it."
    ),
    max_length=BLOG_POST_TOPIC_MAX_LEN,
    examples=["Design"],
)


# ============================== block schemas ============================== #


class BlogHtmlBlockSchema(BaseModel):
    """Read-side projection of an HTML blog block."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "html",
                    "oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                    "position": 0,
                    "html": "<p>Hello, world.</p>",
                },
            ],
        },
    )

    type: Literal[BlogPostBlockType.HTML] = Field(
        default=BlogPostBlockType.HTML,
        description="Discriminator — always `html` for this schema.",
    )
    oid: UUID = Field(description="Block UUID.")
    position: int = Field(
        description="0-based order of the block within the post.",
        ge=0,
    )
    html: str = Field(
        description=(
            "Server-sanitized HTML body. Render directly. Max "
            f"{BLOG_HTML_BLOCK_MAX_LEN} chars (`BLOG_HTML_BLOCK_MAX_LEN`)."
        ),
        max_length=BLOG_HTML_BLOCK_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: BlogHtmlBlockView) -> Self:
        return cls.model_validate(view)


class BlogImageBlockSchema(BaseModel):
    """Read-side projection of an image blog block.

    ``file`` carries a short-lived presigned URL the SPA renders via
    ``<img>``; it is `null` only in the brief window after the backing
    file was soft-deleted but the block row hasn't been cascaded yet.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "image",
                    "oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                    "position": 1,
                    "file": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "content_type": "image/jpeg",
                        "size_bytes": 184_320,
                        "url": "https://s3.example.com/learnic/...",
                    },
                    "caption": "Our team at the launch event",
                },
            ],
        },
    )

    type: Literal[BlogPostBlockType.IMAGE] = Field(
        default=BlogPostBlockType.IMAGE,
        description="Discriminator — always `image` for this schema.",
    )
    oid: UUID = Field(description="Block UUID.")
    position: int = Field(
        description="0-based order of the block within the post.",
        ge=0,
    )
    file: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved image with a short-lived presigned URL, or "
            "`null` if the backing file is gone."
        ),
    )
    caption: str | None = Field(
        default=None,
        description=(
            "Optional caption shown beside the image. Max "
            f"{BLOG_BLOCK_CAPTION_MAX_LEN} chars "
            "(`BLOG_BLOCK_CAPTION_MAX_LEN`)."
        ),
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: BlogImageBlockView) -> Self:
        return cls.model_validate(view)


class BlogVideoBlockSchema(BaseModel):
    """Read-side projection of a video blog block.

    ``file`` carries a short-lived presigned URL the SPA plays via
    ``<video>``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "video",
                    "oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                    "position": 2,
                    "file": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "content_type": "video/mp4",
                        "size_bytes": 52_428_800,
                        "url": "https://s3.example.com/learnic/...",
                    },
                    "title": "Product walkthrough",
                },
            ],
        },
    )

    type: Literal[BlogPostBlockType.VIDEO] = Field(
        default=BlogPostBlockType.VIDEO,
        description="Discriminator — always `video` for this schema.",
    )
    oid: UUID = Field(description="Block UUID.")
    position: int = Field(
        description="0-based order of the block within the post.",
        ge=0,
    )
    file: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved video with a short-lived presigned URL, or "
            "`null` if the backing file is gone."
        ),
    )
    title: str | None = Field(
        default=None,
        description=(
            "Optional title shown beside the player. Max "
            f"{BLOG_BLOCK_CAPTION_MAX_LEN} chars "
            "(`BLOG_BLOCK_CAPTION_MAX_LEN`)."
        ),
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: BlogVideoBlockView) -> Self:
        return cls.model_validate(view)


_BlogPostBlockSchemaUnion = (
    BlogHtmlBlockSchema | BlogImageBlockSchema | BlogVideoBlockSchema
)

BlogPostBlockSchema = Annotated[
    _BlogPostBlockSchemaUnion,
    Discriminator("type"),
]


def _block_view_to_schema(
    view: BlogPostBlockView,
) -> _BlogPostBlockSchemaUnion:
    if isinstance(view, BlogHtmlBlockView):
        return BlogHtmlBlockSchema.from_view(view)
    if isinstance(view, BlogImageBlockView):
        return BlogImageBlockSchema.from_view(view)
    return BlogVideoBlockSchema.from_view(view)


# =============================== post schemas =============================== #


class BlogPostAuthorSchema(BaseModel):
    """Resolved author byline embedded in :class:`BlogPostSchema`.

    ``name`` and ``avatar`` come from the post's creating administrator.
    The whole object is ``null`` on the post when the creating admin's
    account is gone.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Olivia Rhye",
                    "avatar": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "content_type": "image/jpeg",
                        "size_bytes": 84_320,
                        "url": "https://s3.example.com/learnic/avatars/...",
                    },
                },
            ],
        },
    )

    name: str = Field(
        description="Author display name (the creating admin's full name).",
        examples=["Olivia Rhye"],
    )
    avatar: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved author avatar with a short-lived presigned URL, "
            "or `null` when the author has no avatar — the SPA falls "
            "back to an initials avatar."
        ),
    )


class BlogPostSummarySchema(BaseModel):
    """Lightweight post projection for index endpoints (no blocks)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "title": "Announcing our new note platform",
                    "slug": "announcing-our-new-note-platform",
                    "status": "published",
                    "created_at": "2026-05-29T10:00:00Z",
                    "updated_at": "2026-05-29T12:00:00Z",
                    "published_at": "2026-05-29T12:00:00Z",
                    "cover": None,
                },
            ],
        },
    )

    oid: UUID = Field(description="Post UUID.")
    title: str = Field(
        description="Post title.",
        max_length=BLOG_POST_TITLE_MAX_LEN,
    )
    slug: str = Field(
        description="URL slug.",
        max_length=BLOG_POST_SLUG_MAX_LEN,
    )
    status: BlogPostStatus = Field(
        description="Lifecycle status: `draft` or `published`.",
    )
    created_at: datetime = Field(
        description="ISO-8601 UTC creation timestamp.",
    )
    updated_at: datetime = Field(
        description="ISO-8601 UTC last-update timestamp.",
    )
    published_at: datetime | None = Field(
        default=None,
        description=("ISO-8601 UTC publish timestamp, or `null` while in draft."),
    )
    cover: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved cover image with a short-lived presigned URL, or "
            "`null` when the post has no cover — the SPA falls back to a "
            "brand placeholder. The URL expires; re-fetch the list to "
            "get a fresh one."
        ),
    )

    @classmethod
    def from_view(cls, view: BlogPostSummaryView) -> Self:
        return cls.model_validate(view)


class BlogPostSchema(BaseModel):
    """Full post projection: metadata plus the ordered block list."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "title": "Announcing our new note platform",
                    "slug": "announcing-our-new-note-platform",
                    "status": "published",
                    "created_at": "2026-05-29T10:00:00Z",
                    "updated_at": "2026-05-29T12:00:00Z",
                    "published_at": "2026-05-29T12:00:00Z",
                    "cover": None,
                    "blocks": [
                        {
                            "type": "html",
                            "oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                            "position": 0,
                            "html": "<p>Hello, world.</p>",
                        },
                    ],
                },
            ],
        },
    )

    oid: UUID = Field(description="Post UUID.")
    title: str = Field(
        description="Post title.",
        max_length=BLOG_POST_TITLE_MAX_LEN,
    )
    slug: str = Field(
        description="URL slug.",
        max_length=BLOG_POST_SLUG_MAX_LEN,
    )
    status: BlogPostStatus = Field(
        description="Lifecycle status: `draft` or `published`.",
    )
    created_at: datetime = Field(
        description="ISO-8601 UTC creation timestamp.",
    )
    updated_at: datetime = Field(
        description="ISO-8601 UTC last-update timestamp.",
    )
    published_at: datetime | None = Field(
        default=None,
        description=("ISO-8601 UTC publish timestamp, or `null` while in draft."),
    )
    cover: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved cover image with a short-lived presigned URL, or "
            "`null` when the post has no cover — the SPA falls back to a "
            "brand placeholder. The URL expires; re-fetch the post to "
            "get a fresh one."
        ),
    )
    subtitle: str | None = Field(
        default=None,
        description=(
            "Optional short description shown under the title. Max "
            f"{BLOG_POST_SUBTITLE_MAX_LEN} chars "
            "(`BLOG_POST_SUBTITLE_MAX_LEN`), or `null`."
        ),
        max_length=BLOG_POST_SUBTITLE_MAX_LEN,
    )
    topic: str | None = Field(
        default=None,
        description=(
            "Optional topic / category label shown above the title. Max "
            f"{BLOG_POST_TOPIC_MAX_LEN} chars (`BLOG_POST_TOPIC_MAX_LEN`), "
            "or `null`."
        ),
        max_length=BLOG_POST_TOPIC_MAX_LEN,
    )
    author: BlogPostAuthorSchema | None = Field(
        default=None,
        description=(
            "Resolved author byline (the creating admin's name + avatar "
            "plus the editorial role line), or `null` when the creating "
            "admin's account is gone."
        ),
    )
    blocks: list[BlogPostBlockSchema] = Field(
        description=(
            "Ordered content blocks (by `position`). Each is one of "
            "`html`, `image`, or `video` — discriminated by `type`."
        ),
    )

    @classmethod
    def from_view(cls, view: BlogPostView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            slug=view.slug,
            status=view.status,
            created_at=view.created_at,
            updated_at=view.updated_at,
            published_at=view.published_at,
            cover=(
                FileSchema.model_validate(view.cover)
                if view.cover is not None
                else None
            ),
            subtitle=view.subtitle,
            topic=view.topic,
            author=(
                BlogPostAuthorSchema.model_validate(view.author)
                if view.author is not None
                else None
            ),
            blocks=[_block_view_to_schema(block) for block in view.blocks],
        )


# =============================== request bodies ============================= #


class CreateBlogPostSchema(BaseModel):
    """Body for `POST /admin/blog/posts`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Announcing our new note platform",
                    "slug": "announcing-our-new-note-platform",
                },
            ],
        },
    )

    title: str = _TITLE_FIELD
    slug: str = _SLUG_FIELD


class RenameBlogPostSchema(BaseModel):
    """Body for `PATCH /admin/blog/posts/{post_id}/title`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"title": "Updated title"}]},
    )

    title: str = _TITLE_FIELD


class ChangeBlogPostSlugSchema(BaseModel):
    """Body for `PATCH /admin/blog/posts/{post_id}/slug`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"slug": "updated-slug"}]},
    )

    slug: str = _SLUG_FIELD


class EditBlogPostMetaSchema(BaseModel):
    """Body for `PATCH /admin/blog/posts/{post_id}/meta`.

    Sets the post's editorial metadata wholesale: the topic (category
    label above the title) and the short description (under the title).
    Both fields are optional; `null` or a blank string clears the
    corresponding field. The author's name and avatar are not set here —
    they come from the post's creating administrator.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "topic": "Design",
                    "subtitle": (
                        "How do you create compelling presentations that "
                        "wow your colleagues and impress your managers?"
                    ),
                },
            ],
        },
    )

    subtitle: str | None = _SUBTITLE_FIELD
    topic: str | None = _TOPIC_FIELD


class AddBlogHtmlBlockSchema(BaseModel):
    """Body for `POST /admin/blog/posts/{post_id}/blocks/html`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"html": "<p>Hello, world.</p>"}]},
    )

    html: str = Field(
        description=(
            "Raw HTML body; sanitized server-side before storage. Max "
            f"{BLOG_HTML_BLOCK_MAX_LEN} chars (`BLOG_HTML_BLOCK_MAX_LEN`)."
        ),
        max_length=BLOG_HTML_BLOCK_MAX_LEN,
        examples=["<p>Hello, world.</p>"],
    )


class UpdateBlogHtmlBlockSchema(BaseModel):
    """Body for `PATCH /admin/blog/posts/{post_id}/blocks/{block_id}/html`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"html": "<p>Edited.</p>"}]},
    )

    html: str = Field(
        description=(
            "New raw HTML body; sanitized server-side. Max "
            f"{BLOG_HTML_BLOCK_MAX_LEN} chars (`BLOG_HTML_BLOCK_MAX_LEN`)."
        ),
        max_length=BLOG_HTML_BLOCK_MAX_LEN,
        examples=["<p>Edited.</p>"],
    )


class ReorderBlogPostBlocksSchema(BaseModel):
    """Body for `PUT /admin/blog/posts/{post_id}/blocks/order`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ordered_ids": [
                        "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                        "d4e5f6a7-8b9c-4d0e-1f2a-3b4c5d6e7f80",
                    ],
                },
            ],
        },
    )

    ordered_ids: list[UUID] = Field(
        description=(
            "The post's block ids in the desired order. Must be a "
            "permutation of the post's existing block set — same ids, "
            "no additions or omissions — else HTTP 409 `InvalidReorder`."
        ),
        examples=[["c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"]],
    )


class CreatedBlogPostSchema(BaseModel):
    """Response for `POST /admin/blog/posts`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created (draft) post.",
        examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
    )


# ============================ public read routes ============================ #


@public_router.get(
    "",
    summary="List published blog posts (public index)",
    operation_id="listPublishedBlogPosts",
    response_model=list[BlogPostSummarySchema],
    responses={
        200: {
            "headers": {
                "x-total-count": {
                    "description": (
                        "Total number of published posts (without "
                        "pagination), for `ceil(total / limit)` page "
                        "controls."
                    ),
                    "schema": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
)
async def list_published_posts(
    response: Response,
    interactor: FromDishka[ListPublishedBlogPostsQueryHandler],
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset (rows to skip), `>= 0`.",
        examples=[0],
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`).",
        examples=[20],
    ),
) -> list[BlogPostSummarySchema]:
    """Return the public index of published posts, newest first.

    Args:
        response: Injected response so the handler can set the
            ``X-Total-Count`` header.
        interactor: Injected published-list query handler.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        ``200 OK`` with a list of :class:`BlogPostSummarySchema`
        (no blocks). The ``X-Total-Count`` header carries the
        unpaginated total for page controls.
    """
    result = await interactor.run(
        ListPublishedBlogPostsQuery(
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    response.headers["X-Total-Count"] = str(result.total)
    return [BlogPostSummarySchema.from_view(v) for v in result.items]


@public_router.get(
    "/{slug}",
    summary="Get a published blog post by slug (public)",
    operation_id="getPublishedBlogPost",
    response_model=BlogPostSchema,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_published_post(
    interactor: FromDishka[GetPublishedBlogPostBySlugQueryHandler],
    slug: Annotated[str, _SLUG_PATH],
) -> BlogPostSchema:
    """Return a published post with its ordered blocks, by slug.

    Args:
        interactor: Injected published-by-slug query handler.
        slug: URL slug of the post.

    Returns:
        ``200 OK`` with :class:`BlogPostSchema` (metadata + blocks,
        media URLs presigned).

    Raises:
        EntityNotFoundError: No published post has this slug (draft
            posts are invisible here); HTTP 404.
    """
    view = await interactor.run(
        GetPublishedBlogPostBySlugQuery(slug=slug),
    )
    return BlogPostSchema.from_view(view)


# ============================ admin post routes ============================= #


@admin_router.post(
    "",
    summary="Create a blog post (draft)",
    operation_id="createBlogPost",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedBlogPostSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_SLUG_MAP,
)
async def create_post(
    request: Request,
    payload: CreateBlogPostSchema,
    interactor: FromDishka[CreateBlogPostCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
) -> CreatedBlogPostSchema:
    """Create a new blog post in ``DRAFT`` status. Admin-only.

    Args:
        request: Source of the access cookie.
        payload: Title + slug for the new post.
        interactor: Injected create-post command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.

    Returns:
        ``201 Created`` with the new post's UUID.

    Raises:
        InvalidTokenError: Missing/denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        BlogPostSlugAlreadyTakenError: Slug already used; HTTP 409.
        FieldError: Title/slug invariant violated; HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    oid = await interactor.run(
        CreateBlogPostCommand(
            actor_id=ctx.user_id,
            title=payload.title,
            slug=payload.slug,
        ),
    )
    return CreatedBlogPostSchema(oid=oid)


@admin_router.get(
    "",
    summary="List blog posts in any status (admin)",
    operation_id="listBlogPosts",
    response_model=list[BlogPostSummarySchema],
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
    responses={
        200: {
            "headers": {
                "x-total-count": {
                    "description": (
                        "Total number of posts matching the filter "
                        "(without pagination), for page controls."
                    ),
                    "schema": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
)
async def list_posts(
    request: Request,
    response: Response,
    interactor: FromDishka[ListBlogPostsQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_status: BlogPostStatus | None = Query(
        None,
        alias="status",
        description=(
            "Optional status filter (`draft` / `published`). Omit to "
            "list posts in every status."
        ),
        examples=["draft"],
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset (rows to skip), `>= 0`.",
        examples=[0],
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`).",
        examples=[20],
    ),
) -> list[BlogPostSummarySchema]:
    """List blog posts in any status, newest first. Admin-only.

    Args:
        request: Source of the access cookie.
        response: Injected response for the ``X-Total-Count`` header.
        interactor: Injected admin list query handler.
        admin_auth: Injected admin authenticator.
        post_status: Optional lifecycle-status filter (query param
            ``status``).
        offset: Pagination offset.
        limit: Page size.

    Returns:
        ``200 OK`` with a list of :class:`BlogPostSummarySchema`. The
        ``X-Total-Count`` header carries the unpaginated total.

    Raises:
        InvalidTokenError: Missing/denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
    """
    await admin_auth.authenticate_admin(request)
    result = await interactor.run(
        ListBlogPostsQuery(
            pagination=Pagination(limit=limit, offset=offset),
            status=post_status,
        ),
    )
    response.headers["X-Total-Count"] = str(result.total)
    return [BlogPostSummarySchema.from_view(v) for v in result.items]


@admin_router.get(
    "/{post_id}",
    summary="Get a blog post by id in any status (admin)",
    operation_id="getBlogPost",
    response_model=BlogPostSchema,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def get_post(
    request: Request,
    interactor: FromDishka[GetBlogPostQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> BlogPostSchema:
    """Return any post (draft or published) with its blocks. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected get-post query handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``200 OK`` with :class:`BlogPostSchema`.

    Raises:
        InvalidTokenError: Missing/denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    view = await interactor.run(GetBlogPostQuery(post_id=BlogPostID(post_id)))
    return BlogPostSchema.from_view(view)


@admin_router.patch(
    "/{post_id}/title",
    summary="Rename a blog post",
    operation_id="renameBlogPost",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP,
)
async def rename_post(
    request: Request,
    payload: RenameBlogPostSchema,
    interactor: FromDishka[RenameBlogPostCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Change a post's title. Admin-only.

    Args:
        request: Source of the access cookie.
        payload: New title.
        interactor: Injected rename command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        FieldError: Title invariant violated; HTTP 422.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        RenameBlogPostCommand(
            post_id=BlogPostID(post_id),
            title=payload.title,
        ),
    )


@admin_router.patch(
    "/{post_id}/slug",
    summary="Change a blog post's slug",
    operation_id="changeBlogPostSlug",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_SLUG_MAP,
)
async def change_post_slug(
    request: Request,
    payload: ChangeBlogPostSlugSchema,
    interactor: FromDishka[ChangeBlogPostSlugCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Change a post's URL slug. Admin-only.

    Args:
        request: Source of the access cookie.
        payload: New slug.
        interactor: Injected change-slug command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        BlogPostSlugAlreadyTakenError: Slug already used; HTTP 409.
        FieldError: Slug invariant violated; HTTP 422.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        ChangeBlogPostSlugCommand(
            post_id=BlogPostID(post_id),
            slug=payload.slug,
        ),
    )


@admin_router.patch(
    "/{post_id}/meta",
    summary="Edit a blog post's metadata (topic, description)",
    operation_id="editBlogPostMeta",
    response_model=BlogPostSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP,
)
async def edit_post_meta(
    request: Request,
    payload: EditBlogPostMetaSchema,
    interactor: FromDishka[EditBlogPostMetaCommandHandler],
    get_query: FromDishka[GetBlogPostQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> BlogPostSchema:
    """Set a post's topic and short description. Admin-only.

    The author's name and avatar are derived from the post's creating
    administrator and are not editable here; only the optional ``topic``
    (category label above the title) and ``subtitle`` (short description
    under the title) are set. Both are replaced wholesale — `null` or a
    blank string clears the field.

    Args:
        request: Source of the access cookie.
        payload: New topic and/or description (either may be `null`).
        interactor: Injected edit-meta command handler.
        get_query: Injected query used to return the full updated post
            after the command commits.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``200 OK`` with the full :class:`BlogPostSchema` reflecting the
        updated metadata, so the SPA can ``setQueryData`` instead of
        refetching the post.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        FieldError: Subtitle/author-role invariant violated; HTTP 422.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        EditBlogPostMetaCommand(
            post_id=BlogPostID(post_id),
            subtitle=payload.subtitle,
            topic=payload.topic,
        ),
    )
    view = await get_query.run(GetBlogPostQuery(post_id=BlogPostID(post_id)))
    return BlogPostSchema.from_view(view)


@admin_router.post(
    "/{post_id}/publish",
    summary="Publish a blog post",
    operation_id="publishBlogPost",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP | {BlogPostStatusTransitionError: BLOG_POST_STATUS_RULE},
)
async def publish_post(
    request: Request,
    interactor: FromDishka[PublishBlogPostCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Publish a post (DRAFT -> PUBLISHED), making it public. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected publish command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        BlogPostStatusTransitionError: Post is already published;
            HTTP 409.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(PublishBlogPostCommand(post_id=BlogPostID(post_id)))


@admin_router.post(
    "/{post_id}/unpublish",
    summary="Unpublish a blog post",
    operation_id="unpublishBlogPost",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP | {BlogPostStatusTransitionError: BLOG_POST_STATUS_RULE},
)
async def unpublish_post(
    request: Request,
    interactor: FromDishka[UnpublishBlogPostCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Unpublish a post (PUBLISHED -> DRAFT), hiding it again. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected unpublish command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        BlogPostStatusTransitionError: Post is already a draft;
            HTTP 409.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        UnpublishBlogPostCommand(post_id=BlogPostID(post_id)),
    )


@admin_router.delete(
    "/{post_id}",
    summary="Delete a blog post",
    operation_id="deleteBlogPost",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def delete_post(
    request: Request,
    interactor: FromDishka[DeleteBlogPostCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Hard-delete a post and reclaim its media. Admin-only, irreversible.

    All blocks cascade away; image/video files are soft-deleted and
    purged from object storage.

    Args:
        request: Source of the access cookie.
        interactor: Injected delete-post command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(DeleteBlogPostCommand(post_id=BlogPostID(post_id)))


@admin_router.post(
    "/{post_id}/cover",
    summary="Upload (or replace) a blog post's cover image",
    operation_id="setBlogPostCover",
    status_code=status.HTTP_201_CREATED,
    response_model=BlogPostSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP,
)
async def set_cover(
    request: Request,
    interactor: FromDishka[SetBlogPostCoverCommandHandler],
    get_query: FromDishka[GetBlogPostQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
    file: UploadFile = File(  # noqa: B008
        description=(
            "Cover image bytes; `multipart/form-data` field `file`. "
            "Capped at `BLOG_COVER_MAX_BYTES`; the server reads "
            "`Content-Type` from the upload."
        ),
    ),
) -> BlogPostSchema:
    """Upload (or replace) a post's cover image. Admin-only.

    The previous cover (if any) is soft-deleted in the same
    transaction; only the S3 PUT for the new blob happens
    out-of-band.

    Args:
        request: Source of the access cookie.
        interactor: Injected set-cover command handler.
        get_query: Injected query used to return the full updated post
            after the command commits.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.
        file: ``multipart/form-data`` field ``file`` carrying the cover
            image bytes. Capped at ``BLOG_COVER_MAX_BYTES``.

    Returns:
        ``201 Created`` with the full :class:`BlogPostSchema` carrying
        the freshly resolved cover, so the SPA can ``setQueryData``
        instead of refetching the post.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        FileTooLargeError: Cover payload over ``BLOG_COVER_MAX_BYTES``;
            HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    upload = await open_upload(file, max_bytes=BLOG_COVER_MAX_BYTES)
    await interactor.run(
        SetBlogPostCoverCommand(
            actor_id=ctx.user_id,
            post_id=BlogPostID(post_id),
            upload=upload,
        ),
    )
    view = await get_query.run(GetBlogPostQuery(post_id=BlogPostID(post_id)))
    return BlogPostSchema.from_view(view)


@admin_router.delete(
    "/{post_id}/cover",
    summary="Detach a blog post's cover image",
    operation_id="removeBlogPostCover",
    status_code=status.HTTP_200_OK,
    response_model=BlogPostSchema,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def remove_cover(
    request: Request,
    interactor: FromDishka[RemoveBlogPostCoverCommandHandler],
    get_query: FromDishka[GetBlogPostQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> BlogPostSchema:
    """Detach the post's cover and soft-delete the file row. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected remove-cover command handler.
        get_query: Injected query used to return the full updated post
            after the command commits.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``200 OK`` with the full :class:`BlogPostSchema` reflecting the
        detached cover, so the SPA can ``setQueryData`` instead of
        refetching the post.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        RemoveBlogPostCoverCommand(post_id=BlogPostID(post_id)),
    )
    view = await get_query.run(GetBlogPostQuery(post_id=BlogPostID(post_id)))
    return BlogPostSchema.from_view(view)


# =========================== admin block routes ============================= #


@admin_router.post(
    "/{post_id}/blocks/html",
    summary="Append an HTML block to a blog post",
    operation_id="addBlogHtmlBlock",
    status_code=status.HTTP_201_CREATED,
    response_model=BlogHtmlBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP | {ResourceLimitReachedError: RESOURCE_LIMIT_RULE},
)
async def add_html_block(
    request: Request,
    payload: AddBlogHtmlBlockSchema,
    interactor: FromDishka[AddBlogHtmlBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> BlogHtmlBlockSchema:
    """Append an HTML block (sanitized server-side). Admin-only.

    Args:
        request: Source of the access cookie.
        payload: Raw HTML body.
        interactor: Injected add-HTML-block command handler.
        block_query: Injected query used to return the written block.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``201 Created`` with the new :class:`BlogHtmlBlockSchema`.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        ResourceLimitReachedError: Per-post block cap reached; HTTP 409.
        FieldError: HTML invariant violated; HTTP 422.
    """
    await admin_auth.authenticate_admin(request)
    oid = await interactor.run(
        AddBlogHtmlBlockCommand(
            post_id=BlogPostID(post_id),
            html=payload.html,
        ),
    )
    view = await block_query.run(GetBlogPostBlockQuery(block_id=oid))
    assert isinstance(view, BlogHtmlBlockView)  # noqa: S101
    return BlogHtmlBlockSchema.from_view(view)


@admin_router.post(
    "/{post_id}/blocks/image",
    summary="Upload an image and append an image block",
    operation_id="addBlogImageBlock",
    status_code=status.HTTP_201_CREATED,
    response_model=BlogImageBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP
    | {
        ResourceLimitReachedError: RESOURCE_LIMIT_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
    },
)
async def add_image_block(
    request: Request,
    interactor: FromDishka[AddBlogImageBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
    file: UploadFile = File(  # noqa: B008
        description="Image bytes; content type must start with `image/`.",
    ),
    caption: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
        description=(
            "Optional caption shown beside the image. Max "
            f"{BLOG_BLOCK_CAPTION_MAX_LEN} chars "
            "(`BLOG_BLOCK_CAPTION_MAX_LEN`)."
        ),
    ),
) -> BlogImageBlockSchema:
    """Upload an image and append an image block. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected add-image-block command handler.
        block_query: Injected query used to return the written block.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.
        file: ``multipart/form-data`` field ``file`` carrying the
            image bytes. Capped at ``BLOG_IMAGE_BLOCK_MAX_BYTES``;
            content type must start with ``image/``.
        caption: ``multipart/form-data`` field ``caption``; optional.

    Returns:
        ``201 Created`` with the new :class:`BlogImageBlockSchema`
        (presigned image URL included).

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        ResourceLimitReachedError: Per-post block cap reached; HTTP 409.
        WrongFileContentTypeError: File is not an image; HTTP 415.
        FieldError: Caption invariant or file-too-large; HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    upload = await open_upload(file, max_bytes=BLOG_IMAGE_BLOCK_MAX_BYTES)
    oid = await interactor.run(
        AddBlogImageBlockCommand(
            actor_id=ctx.user_id,
            post_id=BlogPostID(post_id),
            upload=upload,
            caption=caption,
        ),
    )
    view = await block_query.run(GetBlogPostBlockQuery(block_id=oid))
    assert isinstance(view, BlogImageBlockView)  # noqa: S101
    return BlogImageBlockSchema.from_view(view)


@admin_router.post(
    "/{post_id}/blocks/video",
    summary="Upload a video and append a video block",
    operation_id="addBlogVideoBlock",
    status_code=status.HTTP_201_CREATED,
    response_model=BlogVideoBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP
    | {
        ResourceLimitReachedError: RESOURCE_LIMIT_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
    },
)
async def add_video_block(
    request: Request,
    interactor: FromDishka[AddBlogVideoBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
    file: UploadFile = File(  # noqa: B008
        description="Video bytes; content type must start with `video/`.",
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
        description=(
            "Optional title shown beside the player. Max "
            f"{BLOG_BLOCK_CAPTION_MAX_LEN} chars "
            "(`BLOG_BLOCK_CAPTION_MAX_LEN`)."
        ),
    ),
) -> BlogVideoBlockSchema:
    """Upload a video and append a video block. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected add-video-block command handler.
        block_query: Injected query used to return the written block.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.
        file: ``multipart/form-data`` field ``file`` carrying the
            video bytes. Capped at ``BLOG_VIDEO_BLOCK_MAX_BYTES``;
            content type must start with ``video/``.
        title: ``multipart/form-data`` field ``title``; optional.

    Returns:
        ``201 Created`` with the new :class:`BlogVideoBlockSchema`
        (presigned video URL included).

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        ResourceLimitReachedError: Per-post block cap reached; HTTP 409.
        WrongFileContentTypeError: File is not a video; HTTP 415.
        FieldError: Title invariant or file-too-large; HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    upload = await open_upload(file, max_bytes=BLOG_VIDEO_BLOCK_MAX_BYTES)
    oid = await interactor.run(
        AddBlogVideoBlockCommand(
            actor_id=ctx.user_id,
            post_id=BlogPostID(post_id),
            upload=upload,
            title=title,
        ),
    )
    view = await block_query.run(GetBlogPostBlockQuery(block_id=oid))
    assert isinstance(view, BlogVideoBlockView)  # noqa: S101
    return BlogVideoBlockSchema.from_view(view)


@admin_router.patch(
    "/{post_id}/blocks/{block_id}/html",
    summary="Update an HTML block's body",
    operation_id="updateBlogHtmlBlock",
    response_model=BlogHtmlBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_html_block(
    request: Request,
    payload: UpdateBlogHtmlBlockSchema,
    interactor: FromDishka[UpdateBlogHtmlBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],  # noqa: ARG001
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> BlogHtmlBlockSchema:
    """Replace an HTML block's body (sanitized server-side). Admin-only.

    Args:
        request: Source of the access cookie.
        payload: New raw HTML body.
        interactor: Injected update-HTML-block command handler.
        block_query: Injected query used to return the updated block.
        admin_auth: Injected admin authenticator.
        post_id: Owning post UUID (URL framing only).
        block_id: Target block UUID.

    Returns:
        ``200 OK`` with the updated :class:`BlogHtmlBlockSchema`.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No block with this id; HTTP 404.
        WrongBlockTypeError: Block isn't of type `html`; HTTP 409.
        FieldError: HTML invariant violated; HTTP 422.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        UpdateBlogHtmlBlockCommand(
            block_id=BlogPostBlockID(block_id),
            html=payload.html,
        ),
    )
    view = await block_query.run(
        GetBlogPostBlockQuery(block_id=BlogPostBlockID(block_id)),
    )
    assert isinstance(view, BlogHtmlBlockView)  # noqa: S101
    return BlogHtmlBlockSchema.from_view(view)


@admin_router.patch(
    "/{post_id}/blocks/{block_id}/image",
    summary="Replace an image block's file and/or caption",
    operation_id="updateBlogImageBlock",
    response_model=BlogImageBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP
    | {
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
    },
)
async def update_image_block(
    request: Request,
    interactor: FromDishka[UpdateBlogImageBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],  # noqa: ARG001
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
    file: UploadFile | None = File(  # noqa: B008
        default=None,
        description="New image bytes. Omit to update only the caption.",
    ),
    caption: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
        description="New caption, or omit to clear the existing one.",
    ),
) -> BlogImageBlockSchema:
    """Replace an image block's file, caption, or both. Admin-only.

    ``file`` omitted keeps the current image; ``caption`` omitted
    clears it.

    Args:
        request: Source of the access cookie.
        interactor: Injected update-image-block command handler.
        block_query: Injected query used to return the updated block.
        admin_auth: Injected admin authenticator.
        post_id: Owning post UUID (URL framing only).
        block_id: Target block UUID.
        file: Optional new image bytes (``image/`` content type).
        caption: Optional new caption.

    Returns:
        ``200 OK`` with the updated :class:`BlogImageBlockSchema`.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No block with this id; HTTP 404.
        WrongBlockTypeError: Block isn't of type `image`; HTTP 409.
        WrongFileContentTypeError: File is not an image; HTTP 415.
        FieldError: Caption invariant or file-too-large; HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    upload = (
        await open_upload(file, max_bytes=BLOG_IMAGE_BLOCK_MAX_BYTES)
        if file is not None
        else None
    )
    await interactor.run(
        UpdateBlogImageBlockCommand(
            actor_id=ctx.user_id,
            block_id=BlogPostBlockID(block_id),
            upload=upload,
            caption=caption,
        ),
    )
    view = await block_query.run(
        GetBlogPostBlockQuery(block_id=BlogPostBlockID(block_id)),
    )
    assert isinstance(view, BlogImageBlockView)  # noqa: S101
    return BlogImageBlockSchema.from_view(view)


@admin_router.patch(
    "/{post_id}/blocks/{block_id}/video",
    summary="Replace a video block's file and/or title",
    operation_id="updateBlogVideoBlock",
    response_model=BlogVideoBlockSchema,
    dependencies=_AUTH_SECURITY,
    error_map=BLOG_ADMIN_FIELD_MAP
    | {
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
    },
)
async def update_video_block(
    request: Request,
    interactor: FromDishka[UpdateBlogVideoBlockCommandHandler],
    block_query: FromDishka[GetBlogPostBlockQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],  # noqa: ARG001
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
    file: UploadFile | None = File(  # noqa: B008
        default=None,
        description="New video bytes. Omit to update only the title.",
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOG_BLOCK_CAPTION_MAX_LEN,
        description="New title, or omit to clear the existing one.",
    ),
) -> BlogVideoBlockSchema:
    """Replace a video block's file, title, or both. Admin-only.

    ``file`` omitted keeps the current video; ``title`` omitted clears
    it.

    Args:
        request: Source of the access cookie.
        interactor: Injected update-video-block command handler.
        block_query: Injected query used to return the updated block.
        admin_auth: Injected admin authenticator.
        post_id: Owning post UUID (URL framing only).
        block_id: Target block UUID.
        file: Optional new video bytes (``video/`` content type).
        title: Optional new title.

    Returns:
        ``200 OK`` with the updated :class:`BlogVideoBlockSchema`.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No block with this id; HTTP 404.
        WrongBlockTypeError: Block isn't of type `video`; HTTP 409.
        WrongFileContentTypeError: File is not a video; HTTP 415.
        FieldError: Title invariant or file-too-large; HTTP 422.
    """
    ctx = await admin_auth.authenticate_admin(request)
    upload = (
        await open_upload(file, max_bytes=BLOG_VIDEO_BLOCK_MAX_BYTES)
        if file is not None
        else None
    )
    await interactor.run(
        UpdateBlogVideoBlockCommand(
            actor_id=ctx.user_id,
            block_id=BlogPostBlockID(block_id),
            upload=upload,
            title=title,
        ),
    )
    view = await block_query.run(
        GetBlogPostBlockQuery(block_id=BlogPostBlockID(block_id)),
    )
    assert isinstance(view, BlogVideoBlockView)  # noqa: S101
    return BlogVideoBlockSchema.from_view(view)


@admin_router.delete(
    "/{post_id}/blocks/{block_id}",
    summary="Delete a blog-post block",
    operation_id="deleteBlogPostBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def delete_block(
    request: Request,
    interactor: FromDishka[DeleteBlogPostBlockCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],  # noqa: ARG001
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Delete a block; reclaim its backing file if any. Admin-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected delete-block command handler.
        admin_auth: Injected admin authenticator.
        post_id: Owning post UUID (URL framing only).
        block_id: Target block UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No block with this id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        DeleteBlogPostBlockCommand(block_id=BlogPostBlockID(block_id)),
    )


@admin_router.put(
    "/{post_id}/blocks/order",
    summary="Reorder a blog post's blocks",
    operation_id="reorderBlogPostBlocks",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP | {InvalidReorderError: INVALID_REORDER_RULE},
)
async def reorder_blocks(
    request: Request,
    payload: ReorderBlogPostBlocksSchema,
    interactor: FromDishka[ReorderBlogPostBlocksCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    post_id: Annotated[UUID, _POST_ID_PATH],
) -> None:
    """Replace the block ordering within a post atomically. Admin-only.

    Args:
        request: Source of the access cookie.
        payload: The post's block ids in the desired order.
        interactor: Injected reorder command handler.
        admin_auth: Injected admin authenticator.
        post_id: Target post UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotAdminError: HTTP 403.
        EntityNotFoundError: No post with this id; HTTP 404.
        InvalidReorderError: ``ordered_ids`` isn't a permutation of the
            post's blocks; HTTP 409.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(
        ReorderBlogPostBlocksCommand(
            post_id=BlogPostID(post_id),
            ordered_ids=[BlogPostBlockID(oid) for oid in payload.ordered_ids],
        ),
    )
