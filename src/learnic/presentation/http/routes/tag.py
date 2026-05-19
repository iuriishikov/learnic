"""Tag HTTP routes — global tag pool + per-product attachments.

Tags are global and shared: any authenticated user can search the
pool, and any user with ``edit_description`` on a product can
attach existing tags or mint new ones via the get-or-create path
on ``PUT /products/{product_id}/tags``. Real-time deltas land on
the product event channel (``tags_changed``); see the
``## WebSocket channels`` section in the OpenAPI description.
"""

from typing import Annotated, Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_extra_types.color import Color

from learnic.application.commands.product.update_tags import (
    ExistingTagSpec,
    NewTagSpec,
    TagSpec,
    UpdateProductTagsCommand,
    UpdateProductTagsCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.common.persistence.tag import TagView
from learnic.application.queries.tag.list import (
    ListProductTagsQuery,
    ListProductTagsQueryHandler,
)
from learnic.application.queries.tag.search import (
    SearchTagsQuery,
    SearchTagsQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.tag.constants import (
    PRODUCT_TAGS_MAX,
    TAG_COLOR_MAX_LEN,
    TAG_NAME_MAX_LEN,
    TAG_NAME_MIN_LEN,
)
from learnic.entities.tag.ids import TagID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

tag_router = ErrorAwareRouter(
    prefix="/tags",
    tags=["Tags"],
    route_class=DishkaErrorAwareRoute,
)

product_tags_router = ErrorAwareRouter(
    prefix="/products/{product_id}/tags",
    tags=["Tags"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


# --------------------------- request schemas --------------------------- #


class ExistingTagItemSchema(BaseModel):
    """Existing-tag branch of the ``PUT`` body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"tag_id": "f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b"}],
        },
    )

    tag_id: UUID = Field(
        description="Existing tag UUID to attach to the product.",
        examples=["f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b"],
    )


class NewTagItemSchema(BaseModel):
    """New-tag branch of the ``PUT`` body (get-or-create).

    The server matches by case-insensitive whitespace-collapsed
    slug — if a tag with the same effective name already exists
    in the global pool, it is reused regardless of the ``color``
    field. Otherwise a fresh tag is inserted with the supplied
    color (normalised to its hex form).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"name": "Python", "color": "#3776ab"}],
        },
    )

    name: str = Field(
        description=(
            "Display name of a brand new tag. Length is "
            f"`{TAG_NAME_MIN_LEN}..{TAG_NAME_MAX_LEN}` "
            "(`TAG_NAME_MIN_LEN`/`TAG_NAME_MAX_LEN`)."
        ),
        min_length=TAG_NAME_MIN_LEN,
        max_length=TAG_NAME_MAX_LEN,
        examples=["Python", "Алгоритмы"],
    )
    color: str = Field(
        description=(
            "Any CSS color string accepted by "
            "`pydantic_extra_types.color.Color` — hex (`#fff`, "
            "`#ffffff`, `#ffffffff`), CSS named (`red`, "
            "`rebeccapurple`), or `rgb()`/`rgba()`/`hsl()`/`hsla()`. "
            "The server normalises to hex before storage. Max "
            "length `TAG_COLOR_MAX_LEN`."
        ),
        min_length=1,
        max_length=TAG_COLOR_MAX_LEN,
        examples=["#3776ab", "rgb(55, 118, 171)", "rebeccapurple"],
    )

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        # ``Color(...)`` raises ``PydanticCustomError`` already on
        # bad input, which fastapi-error-map translates to 422. The
        # canonical hex form removes case / format jitter — two
        # clients typing ``"#f00"`` and ``"red"`` converge on the
        # same stored value.
        return Color(value).as_hex()


TagItemSchema = ExistingTagItemSchema | NewTagItemSchema


class UpdateProductTagsSchema(BaseModel):
    """Body for ``PUT /products/{product_id}/tags``.

    Replaces the product's tag set in one shot. Each item is
    either an existing tag id or a new ``{name, color}`` pair —
    the SPA does not have to make a separate "create tag" call
    before attaching. Duplicates within ``items`` collapse to the
    first occurrence; the list ordering survives storage.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {"tag_id": "f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b"},
                        {"name": "Python", "color": "#3776ab"},
                    ],
                },
            ],
        },
    )

    items: list[TagItemSchema] = Field(
        description=(
            "Ordered list of tags to attach. Up to "
            f"`{PRODUCT_TAGS_MAX}` items per product "
            "(`PRODUCT_TAGS_MAX`). Each item is either a "
            "reference to an existing tag (`tag_id`) or a new "
            "`{name, color}` pair the server upserts by slug."
        ),
        max_length=PRODUCT_TAGS_MAX,
        examples=[
            [
                {"tag_id": "f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b"},
                {"name": "Python", "color": "#3776ab"},
            ],
        ],
    )


# --------------------------- response schemas -------------------------- #


class TagSchema(BaseModel):
    """Tag response projection — the same shape on every tag-emitting endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b",
                    "name": "Python",
                    "color": "#3776ab",
                },
            ],
        },
    )

    oid: UUID
    name: str
    color: str

    @classmethod
    def from_view(cls, view: TagView) -> Self:
        return cls(oid=view.oid, name=view.name, color=view.color)


class TagListSchema(BaseModel):
    """List wrapper for autocomplete responses."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"items": []}]})

    items: list[TagSchema]


class ProductTagsSchema(BaseModel):
    """Response body for ``PUT /products/{product_id}/tags``.

    Mirrors what ``GET /products/{id}.tags`` would return so the
    SPA can drop the array straight into the product cache after
    a successful save.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [{"items": []}]})

    items: list[TagSchema]


# ------------------------------ routes --------------------------------- #


@tag_router.get(
    "",
    summary="Autocomplete the global tag pool",
    operation_id="searchTags",
    response_model=TagListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def search_tags(
    request: Request,
    interactor: FromDishka[SearchTagsQueryHandler],
    auth: FromDishka[Authenticator],
    query: Annotated[
        str,
        Query(
            description=(
                "Case-insensitive substring; empty string returns "
                "the lexicographically first page of the pool."
            ),
            max_length=TAG_NAME_MAX_LEN,
        ),
    ] = "",
    limit: Annotated[
        int,
        Query(
            description=(
                "Page size. Defaults to `DEFAULT_LIMIT`, capped at "
                "`MAX_LIMIT`."
            ),
            ge=1,
            le=MAX_LIMIT,
        ),
    ] = DEFAULT_LIMIT,
    offset: Annotated[
        int,
        Query(description="Skip the first `offset` results.", ge=0),
    ] = 0,
) -> TagListSchema:
    """Return up to ``limit`` tags whose name contains ``query``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected search-tags query handler.
        auth: Injected authenticator.
        query: Substring filter (case-insensitive).
        limit: Page size, defaults to ``DEFAULT_LIMIT``.
        offset: Page offset.

    Returns:
        :class:`TagListSchema` ordered by tag name ascending.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    await auth.authenticate(request)
    views = await interactor.run(
        SearchTagsQuery(
            query=query,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return TagListSchema(items=[TagSchema.from_view(v) for v in views])


@product_tags_router.get(
    "",
    summary="List the tags attached to a product",
    operation_id="listProductTags",
    response_model=ProductTagsSchema,
    error_map={},
)
async def list_product_tags(
    interactor: FromDishka[ListProductTagsQueryHandler],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductTagsSchema:
    """Return the product's tags in author-defined order.

    Public — tag visibility tracks product visibility, and the
    product itself is reachable via the public ``GET /products/{id}``.
    Returns an empty list when the product has none, or when the
    product is unknown (a separate ``GET /products/{id}`` call
    will return 404 in that case; this endpoint stays cheap and
    never 404s on its own).

    Args:
        interactor: Injected list-product-tags query handler.
        product_id: Owning product, parsed from the URL path.

    Returns:
        :class:`ProductTagsSchema` with the tags in
        ``product_tags.position`` order.
    """
    views = await interactor.run(
        ListProductTagsQuery(product_id=ProductID(product_id)),
    )
    return ProductTagsSchema(items=[TagSchema.from_view(v) for v in views])


@product_tags_router.put(
    "",
    summary="Replace the tag list of a product",
    operation_id="updateProductTags",
    response_model=ProductTagsSchema,
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    error_map={
        **AUTHENTICATED_AUTHORIZED_FIELD_MAP,
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
    },
)
async def update_product_tags(
    request: Request,
    payload: UpdateProductTagsSchema,
    interactor: FromDishka[UpdateProductTagsCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductTagsSchema:
    """Replace the tag list of a product in one shot (PUT semantics).

    Mixes existing and new tags in a single body. New ones are
    upserted by slug — two clients typing the same tag name at
    once converge on the same row instead of racing into a
    unique-index conflict. After commit, a ``tags_changed``
    event is published on the product channel.

    Args:
        request: Source of the access-token cookie.
        payload: Ordered list of tag items.
        interactor: Injected update-product-tags command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        :class:`ProductTagsSchema` with the resolved, deduplicated,
        position-ordered tag list — the SPA stores it verbatim.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Product or referenced tag missing; HTTP 404.
        InsufficientPermissionsError: Caller lacks `edit_description`;
            HTTP 403.
        FieldError: ``TagName``/``TagColor`` invariant violated, or
            payload exceeded `PRODUCT_TAGS_MAX` items; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    specs: list[TagSpec] = []
    for item in payload.items:
        if isinstance(item, ExistingTagItemSchema):
            specs.append(ExistingTagSpec(tag_id=TagID(item.tag_id)))
        else:
            # ``color`` is already canonical-hex thanks to the
            # field validator on :class:`NewTagItemSchema`.
            specs.append(NewTagSpec(name=item.name, color=item.color))
    tags = await interactor.run(
        UpdateProductTagsCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            specs=specs,
        ),
    )
    return ProductTagsSchema(
        items=[
            TagSchema(oid=tag.oid, name=tag.name.value, color=tag.color.value)
            for tag in tags
        ],
    )
