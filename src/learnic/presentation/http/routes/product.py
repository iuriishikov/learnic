from datetime import datetime
from typing import Annotated, Final, Self
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
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.product.add_note import (
    AddNoteProductCommand,
    AddNoteProductCommandHandler,
)
from learnic.application.commands.product.archive import (
    ArchiveProductCommand,
    ArchiveProductCommandHandler,
)
from learnic.application.commands.product.change_description import (
    ChangeProductDescriptionCommand,
    ChangeProductDescriptionCommandHandler,
)
from learnic.application.commands.product.change_duration import (
    ChangeProductDurationCommand,
    ChangeProductDurationCommandHandler,
)
from learnic.application.commands.product.change_name import (
    ChangeProductNameCommand,
    ChangeProductNameCommandHandler,
)
from learnic.application.commands.product.change_visibility import (
    ChangeProductVisibilityCommand,
    ChangeProductVisibilityCommandHandler,
)
from learnic.application.commands.product.cover.remove import (
    RemoveProductCoverCommand,
    RemoveProductCoverCommandHandler,
)
from learnic.application.commands.product.cover.set import (
    SetProductCoverCommand,
    SetProductCoverCommandHandler,
)
from learnic.application.commands.product.delete import (
    DeleteProductCommand,
    DeleteProductCommandHandler,
)
from learnic.application.commands.product.publish import (
    PublishProductCommand,
    PublishProductCommandHandler,
)
from learnic.application.commands.product.unarchive import (
    UnarchiveProductCommand,
    UnarchiveProductCommandHandler,
)
from learnic.application.commands.enrollment.enroll_into_product import (
    EnrollIntoProductCommand,
    EnrollIntoProductCommandHandler,
)
from learnic.application.commands.product_qa.add import (
    AddProductQACommand,
    AddProductQACommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInPrivateProductError,
    CannotEnrollInUnpublishedProductError,
    CannotEnrollInUnreleasedNoteError,
    CannotPublishNoteDirectlyError,
    EntityNotFoundError,
    ProductNameAlreadyTakenError,
    ProductNotArchivedError,
    ProductNotInDraftError,
)
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.application.queries.enrollment.list_for_product import (
    GetProductEnrollmentsQuery,
    GetProductEnrollmentsQueryHandler,
)
from learnic.presentation.http.routes.enrollment import (
    EnrollmentSchema,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    SEARCH_QUERY_MAX_LEN,
    SEARCH_QUERY_MIN_LEN,
    Pagination,
)
from learnic.application.common.storage.upload import IncomingUpload
from learnic.application.common.statistics.collector import (
    StatisticsCollector,
)
from learnic.entities.statistic.models import Statistic
from learnic.application.common.persistence.product_qa import ProductQAView
from learnic.application.queries.product.check_name_availability import (
    CheckProductNameAvailabilityQuery,
    CheckProductNameAvailabilityQueryHandler,
)
from learnic.application.queries.product.get import (
    GetProductQuery,
    GetProductQueryHandler,
    ProductOutput,
)
from learnic.application.queries.product.get_my import (
    GetMyProductsQuery,
    GetMyProductsQueryHandler,
)
from learnic.application.queries.product.get_published import (
    GetPublishedProductsQuery,
    GetPublishedProductsQueryHandler,
)
from learnic.application.queries.product.search import (
    SearchPublishedProductsQuery,
    SearchPublishedProductsQueryHandler,
)
from learnic.application.queries.product.search_my import (
    SearchMyProductsQuery,
    SearchMyProductsQueryHandler,
)
from learnic.application.queries.product.recommend_for_me import (
    RecommendForMeQuery,
    RecommendForMeQueryHandler,
)
from learnic.application.queries.product_qa.list import (
    GetProductQAListQuery,
    GetProductQAListQueryHandler,
)
from learnic.entities.product.constants import (
    DESCRIPTION_MAX_LEN,
    DURATION_HOURS_MAX,
    DURATION_HOURS_MIN,
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
    ProductVisibility,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.tag.constants import PRODUCT_TAGS_MAX
from learnic.entities.tag.ids import TagID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.entities.common.limits import ResourceLimitReachedError
from learnic.presentation.http.common.errors.rules import (
    ALREADY_ENROLLED_RULE,
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    CANNOT_ENROLL_IN_PRIVATE_PRODUCT_RULE,
    CANNOT_ENROLL_IN_UNPUBLISHED_PRODUCT_RULE,
    CANNOT_ENROLL_IN_UNRELEASED_NOTE_RULE,
    CANNOT_PUBLISH_NOTE_DIRECTLY_RULE,
    ENTITY_NOT_FOUND_RULE,
    PRODUCT_DOES_NOT_SUPPORT_RULE,
    PRODUCT_NAME_TAKEN_RULE,
    PRODUCT_NOT_ARCHIVED_RULE,
    PRODUCT_NOT_IN_DRAFT_RULE,
    RESOURCE_LIMIT_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.routes.tag import TagSchema
from learnic.presentation.http.common.schemas import (
    FileSchema,
    UserSchema,
)
from learnic.presentation.http.common.upload_limits import (
    PRODUCT_COVER_MAX_BYTES,
)
from learnic.presentation.http.common.uploads import open_upload

router = ErrorAwareRouter(
    prefix="/products",
    tags=["Products"],
    route_class=DishkaErrorAwareRoute,
)

# Note-enrollment endpoints live under /notes (parallel to other
# note-specific routers in note_content.py / note_release.py).
# Listed here for code locality with the rest of product.py — these
# operations still take a ``ProductID`` underneath but the URL surface
# is note-scoped.
note_router = ErrorAwareRouter(
    prefix="/notes",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)

# Caller-scoped views over products (rule 14: live under /users/me).
me_router = ErrorAwareRouter(
    prefix="/users/me",
    tags=["Products"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_NOTE_ID_PATH: Final = Path(
    description="Target note product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


# ---------------------------- request schemas -------------------------- #


class ChangeProductNameSchema(BaseModel):
    """Body for ``PATCH /products/{id}/name``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": "Async Python — 2026 edition"}],
        },
    )

    value: str = Field(
        description=(
            "New product name. Required, non-empty. "
            f"Max length is {TITLE_MAX_LEN} chars "
            "(`TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
        examples=["Async Python — 2026 edition"],
    )


class ChangeProductDescriptionSchema(BaseModel):
    """Body for ``PATCH /products/{id}/description``.

    Incoming HTML is sanitized server-side; unsafe tags and
    attributes are stripped before reaching the domain.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": "<p>Updated outline.</p>"}],
        },
    )

    value: str = Field(
        description=(
            "New description as HTML. Sanitized server-side; "
            f"length limit is {DESCRIPTION_MAX_LEN} chars "
            "(`DESCRIPTION_MAX_LEN`) measured **after** "
            "sanitization."
        ),
        min_length=1,
        max_length=DESCRIPTION_MAX_LEN,
        examples=["<p>Updated outline.</p>"],
    )


class ChangeProductDurationSchema(BaseModel):
    """Body for ``PATCH /products/{id}/duration``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": 35}]},
    )

    value: int = Field(
        description=(
            "New total duration in hours. Must be in "
            f"`[{DURATION_HOURS_MIN}, {DURATION_HOURS_MAX}]`."
        ),
        ge=DURATION_HOURS_MIN,
        le=DURATION_HOURS_MAX,
        examples=[35],
    )


class ChangeProductVisibilitySchema(BaseModel):
    """Body for ``PATCH /products/{id}/visibility``.

    Owner-only — only the product's author may switch visibility; the
    capability is not delegable to collaborators through any role.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"visibility": "private"}]},
    )

    visibility: ProductVisibility = Field(
        description=(
            "Target visibility. `public` allows self-enrollment; "
            "`private` makes the product invite-only — it stays "
            "visible in the catalog/search but self-enroll is refused "
            "and access is granted only through an accepted gift. "
            "Orthogonal to `status`."
        ),
        examples=["public", "private"],
    )


# ---------------------------- response schemas ------------------------- #


class ProductSchema(BaseModel):
    """Full product projection returned by ``GET /products/...``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "type": "note",
                    "status": "published",
                    "visibility": "public",
                    "name": "Async Python deep dive",
                    "description": "<p>A 30-hour note.</p>",
                    "total_duration_in_hours": 30,
                    "author": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "full_name": "Lovelace Ada",
                        "email": "a*****a@example.com",
                        "is_verified": True,
                        "avatar": None,
                    },
                    "cover": {
                        "oid": "11111111-2222-3333-4444-555555555555",
                        "content_type": "image/jpeg",
                        "size_bytes": 184_320,
                        "url": (
                            "https://s3.example.com/products/cover.png"
                            "?X-Amz-Signature=..."
                        ),
                    },
                    "tags": [
                        {
                            "oid": "f0a1b2c3-d4e5-46f7-8a9b-0c1d2e3f4a5b",
                            "name": "Python",
                            "color": "#3776ab",
                        },
                    ],
                    "published_at": "2026-04-01T10:00:00+00:00",
                    "created_at": "2026-03-25T09:00:00+00:00",
                    "updated_at": "2026-04-01T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID
    type: ProductType
    status: ProductStatus
    visibility: ProductVisibility = Field(
        description=(
            "Enrollment visibility, orthogonal to `status`. Both "
            "`public` and `private` products appear in the "
            "catalog/search and on their detail page; the difference "
            "is enrollment. `public` accepts self-enrollment; "
            "`private` is invite-only — self-enroll is refused (409 "
            "`CannotEnrollInPrivateProduct`) and access is granted "
            "only through an accepted gift. The SPA should hide the "
            "self-enroll CTA when `private`. Toggled by the owner via "
            "`PATCH /products/{id}/visibility`."
        ),
        examples=["public", "private"],
    )
    name: str
    description: str | None
    total_duration_in_hours: int | None
    author: UserSchema = Field(
        description=(
            "Product author as the unified public user projection — "
            "identity (id, display name, masked email, verified badge) "
            "plus avatar/cover with presigned URLs. The profile-only "
            "fields (`description`, contact links) are `null` here; "
            "fetch `GET /users/{id}` for the full profile. Same shape "
            "everywhere a user is embedded (collaborators, gifts, "
            "notification actors)."
        ),
    )
    cover: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved cover file with a short-lived presigned URL, "
            "or `null` when no cover is attached. The URL expires; "
            "re-fetch the product resource to get a fresh one."
        ),
    )
    tags: list[TagSchema] = Field(
        default_factory=list,
        description=(
            "Product tags in author-defined order. Embedded inline so "
            "every list/detail/recommendation endpoint already carries "
            "what the chip row needs — no follow-up "
            "`GET /products/{id}/tags` round-trip required."
        ),
    )
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_output(cls, view: ProductOutput) -> Self:
        return cls(
            oid=view.oid,
            type=view.type,
            status=view.status,
            visibility=view.visibility,
            name=view.name,
            description=view.description,
            total_duration_in_hours=view.total_duration_in_hours,
            author=UserSchema.model_validate(view.author),
            cover=(
                FileSchema.model_validate(view.cover)
                if view.cover is not None
                else None
            ),
            tags=[TagSchema.model_validate(t) for t in view.tags],
            published_at=view.published_at,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


class CreatedProductSchema(BaseModel):
    """Response for product-creation endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created product.",
        examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
    )


class ProductNameAvailabilitySchema(BaseModel):
    """Response for ``GET /products/name-availability``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"available": True}]},
    )

    available: bool = Field(
        description=(
            "``true`` when the current user does not yet own a "
            "product with the supplied name. Names are unique "
            "per author across all statuses (including archived) "
            "and are compared case-sensitively; different authors "
            "may share names."
        ),
        examples=[True],
    )


# ------------------------------- routes -------------------------------- #


_NameField = Annotated[
    str,
    Form(
        description=(
            "Product title (multipart form field). "
            f"Max length is {TITLE_MAX_LEN} chars."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
    ),
]
_DescriptionField = Annotated[
    str | None,
    Form(
        description=(
            "Optional product description as HTML, sanitized "
            f"server-side. Max length is {DESCRIPTION_MAX_LEN} chars "
            "after sanitization. Omit to create a draft without a "
            "description."
        ),
        min_length=1,
        max_length=DESCRIPTION_MAX_LEN,
    ),
]
_DurationHoursField = Annotated[
    int | None,
    Form(
        description=(
            "Optional estimated total duration in hours, "
            f"`[{DURATION_HOURS_MIN}, {DURATION_HOURS_MAX}]`. "
            "Omit to create a draft without an estimate."
        ),
        ge=DURATION_HOURS_MIN,
        le=DURATION_HOURS_MAX,
    ),
]
_CoverField = Annotated[
    UploadFile | None,
    File(
        description=(
            "Optional cover image — sent as a `multipart/form-data` "
            "file part. Capped at the file-storage limit; the server "
            "reads `Content-Type` from the upload."
        ),
    ),
]


@router.post(
    "/notes",
    summary="Create a new note product",
    operation_id="addNoteProduct",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedProductSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {
        ProductNameAlreadyTakenError: PRODUCT_NAME_TAKEN_RULE,
        ResourceLimitReachedError: RESOURCE_LIMIT_RULE,
    },
)
async def add_note(
    request: Request,
    interactor: FromDishka[AddNoteProductCommandHandler],
    auth: FromDishka[Authenticator],
    name: _NameField,
    description_html: _DescriptionField = None,
    total_duration_in_hours: _DurationHoursField = None,
    cover: _CoverField = None,
) -> CreatedProductSchema:
    """Create a new note product owned by the current user.

    Only ``name`` is required — every other field is optional and
    can be filled in later via PATCH endpoints. The endpoint
    accepts ``multipart/form-data`` so the cover image can be
    attached in the same request as the metadata fields.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected add-note command handler.
        auth: Injected authenticator that validates the access cookie.
        name: Form field — product title (VO-validated). Required.
        description_html: Optional form field — HTML description
            (sanitized then VO-validated). Omit to leave empty.
        total_duration_in_hours: Optional form field — total duration
            in hours. Omit to leave unset.
        cover: Optional ``multipart/form-data`` file part. Capped at
            ``PRODUCT_COVER_MAX_BYTES``; the server reads
            ``Content-Type`` from the upload.

    Returns:
        ``201 Created`` with the new product's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        ProductNameAlreadyTakenError: The current author already has
            a product with this name; HTTP 409.
        FieldError: Value-object invariants violated; HTTP 422.
        FileTooLargeError: Cover payload over
            ``PRODUCT_COVER_MAX_BYTES``; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    cover_upload = await _read_optional_cover(cover)
    oid = await interactor.run(
        AddNoteProductCommand(
            author_id=ctx.user_id,
            name=name,
            description_html=description_html,
            total_duration_in_hours=total_duration_in_hours,
            cover=cover_upload,
        ),
    )
    return CreatedProductSchema(oid=oid)


async def _read_optional_cover(
    upload: UploadFile | None,
) -> IncomingUpload | None:
    """Open an optional cover ``UploadFile`` as an ``IncomingUpload``.

    Returns ``None`` when nothing was uploaded so the handler can
    skip the file-creation branch entirely. Uses
    ``PRODUCT_COVER_MAX_BYTES`` to match the dedicated set-cover
    endpoint — keep the two in lockstep. The returned upload exposes
    ``.size`` / ``.content_type`` and streams its bytes on demand.
    """
    if upload is None:
        return None
    return await open_upload(
        upload, max_bytes=PRODUCT_COVER_MAX_BYTES,
    )


@router.patch(
    "/{product_id}/name",
    summary="Change a product's name",
    operation_id="changeProductName",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductNameAlreadyTakenError: PRODUCT_NAME_TAKEN_RULE},
)
async def change_name(
    request: Request,
    payload: ChangeProductNameSchema,
    interactor: FromDishka[ChangeProductNameCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Replace the product's name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new name>"}``.
        interactor: Injected change-name command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ProductNameAlreadyTakenError: The current author already has
            a product with this name; HTTP 409.
        FieldError: ``ProductTitle`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductNameCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{product_id}/description",
    summary="Change a product's HTML description",
    operation_id="changeProductDescription",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_description(
    request: Request,
    payload: ChangeProductDescriptionSchema,
    interactor: FromDishka[ChangeProductDescriptionCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Replace the product's HTML description (sanitized server-side).

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<html>..."}``; sanitized before
            reaching the domain.
        interactor: Injected change-description command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        FieldError: Sanitized description empty or too long; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductDescriptionCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            html=payload.value,
        ),
    )


@router.patch(
    "/{product_id}/duration",
    summary="Change a product's total duration in hours",
    operation_id="changeProductDuration",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_duration(
    request: Request,
    payload: ChangeProductDurationSchema,
    interactor: FromDishka[ChangeProductDurationCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Replace the product's total duration estimate.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": <hours>}``.
        interactor: Injected change-duration command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        FieldError: ``DurationHours`` VO invariants violated;
            HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductDurationCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{product_id}/visibility",
    summary="Switch a product between public and private (owner only)",
    operation_id="changeProductVisibility",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_visibility(
    request: Request,
    payload: ChangeProductVisibilitySchema,
    interactor: FromDishka[ChangeProductVisibilityCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Set the product's discovery visibility (public ⇄ private).

    Owner-only: only the product's author may toggle visibility, and —
    unlike the other editing routes — the gate is **ownership**, not a
    permission. No collaborator role can grant it, so a non-author
    (collaborator included) always gets ``403 NotResourceOwner``.
    Visibility is orthogonal to lifecycle ``status``: a ``PUBLISHED``
    product can be made ``PRIVATE`` without unpublishing it. A
    ``PRIVATE`` product stays fully visible in the catalog/search and
    on its detail page — switching only blocks **self-enrollment**
    (the product becomes invite-only, joinable through a gift);
    existing enrollments and gift access are untouched. Idempotent —
    re-applying the current visibility is a no-op.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"visibility": "public" | "private"}``.
        interactor: Injected change-visibility command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductVisibilityCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            visibility=payload.visibility,
        ),
    )


@router.post(
    "/{product_id}/cover",
    summary="Upload (or replace) a product's cover image",
    operation_id="setProductCover",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=ProductSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def set_cover(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetProductCoverCommandHandler],
    get_query: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Upload (or replace) a product's cover image.

    The previous cover (if any) is soft-deleted in the same
    transaction; only the S3 PUT for the new blob happens
    out-of-band.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` carrying the
            image bytes. Capped at ``PRODUCT_COVER_MAX_BYTES``; the
            server reads ``Content-Type`` from the upload and rejects
            payloads above the limit with a 422 ``FileTooLargeError``.
        interactor: Injected set-cover command handler.
        get_query: Injected query handler used to return the full
            updated product after the command commits.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the full :class:`ProductSchema` carrying
        the freshly resolved cover. The SPA can ``setQueryData``
        directly instead of refetching ``GET /products/{id}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        FieldError: Cover VO invariants violated; HTTP 422.
        FileTooLargeError: Payload over ``PRODUCT_COVER_MAX_BYTES``;
            HTTP 422.
    """
    ctx = await auth.authenticate(request)
    upload = await open_upload(
        file, max_bytes=PRODUCT_COVER_MAX_BYTES,
    )
    await interactor.run(
        SetProductCoverCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            upload=upload,
        ),
    )
    view = await get_query.run(GetProductQuery(oid=ProductID(product_id)))
    return ProductSchema.from_output(view)


@router.delete(
    "/{product_id}/cover",
    summary="Detach a product's cover image",
    operation_id="removeProductCover",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=ProductSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def remove_cover(
    request: Request,
    interactor: FromDishka[RemoveProductCoverCommandHandler],
    get_query: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Detach the product's cover and soft-delete the file row.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-cover command handler.
        get_query: Injected query handler used to return the full
            updated product after the command commits.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``200 OK`` with the full :class:`ProductSchema` reflecting
        the detached cover so the SPA can ``setQueryData`` instead
        of refetching ``GET /products/{id}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RemoveProductCoverCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    view = await get_query.run(GetProductQuery(oid=ProductID(product_id)))
    return ProductSchema.from_output(view)


@router.post(
    "/{product_id}/publish",
    summary="Publish a product directly",
    operation_id="publishProduct",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=ProductSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {CannotPublishNoteDirectlyError: CANNOT_PUBLISH_NOTE_DIRECTLY_RULE},
)
async def publish(
    request: Request,
    interactor: FromDishka[PublishProductCommandHandler],
    get_query: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Mark a product published.

    Note products cannot be published via this endpoint — they
    are published implicitly by creating their first release
    (``POST /products/{id}/releases``). Direct publish on a
    note returns HTTP 409 ``CannotPublishNoteDirectly``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected publish command handler.
        get_query: Injected query handler used to return the full
            updated product after the command commits.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``200 OK`` with the full :class:`ProductSchema` reflecting
        the published status so the SPA can ``setQueryData`` instead
        of refetching ``GET /products/{id}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        CannotPublishNoteDirectlyError: Product is a note;
            HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        PublishProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    view = await get_query.run(GetProductQuery(oid=ProductID(product_id)))
    return ProductSchema.from_output(view)


@router.post(
    "/{product_id}/archive",
    summary="Archive a product",
    operation_id="archiveProduct",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=ProductSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def archive(
    request: Request,
    interactor: FromDishka[ArchiveProductCommandHandler],
    get_query: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Move the product into the archived state.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected archive command handler.
        get_query: Injected query handler used to return the full
            updated product after the command commits.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``200 OK`` with the full :class:`ProductSchema` reflecting
        the archived status so the SPA can ``setQueryData`` instead
        of refetching ``GET /products/{id}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ArchiveProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    view = await get_query.run(GetProductQuery(oid=ProductID(product_id)))
    return ProductSchema.from_output(view)


@router.post(
    "/{product_id}/unarchive",
    summary="Restore an archived product",
    operation_id="unarchiveProduct",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=ProductSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductNotArchivedError: PRODUCT_NOT_ARCHIVED_RULE},
)
async def unarchive(
    request: Request,
    interactor: FromDishka[UnarchiveProductCommandHandler],
    get_query: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Move an archived product back to its prior lifecycle state.

    The target status is derived from ``published_at``: a non-null
    value means the product was previously published (webinar via
    ``POST /products/{id}/publish``, note via its first release)
    and the product returns to ``published``; otherwise it returns
    to ``draft``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected unarchive command handler.
        get_query: Injected query handler used to return the full
            updated product after the command commits.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``200 OK`` with the full :class:`ProductSchema` reflecting
        the restored status so the SPA can ``setQueryData`` instead
        of refetching ``GET /products/{id}``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ProductNotArchivedError: Product is not currently archived;
            HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UnarchiveProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    view = await get_query.run(GetProductQuery(oid=ProductID(product_id)))
    return ProductSchema.from_output(view)


@router.delete(
    "/{product_id}",
    summary="Delete a draft product",
    operation_id="deleteProduct",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductNotInDraftError: PRODUCT_NOT_IN_DRAFT_RULE},
)
async def delete_product(
    request: Request,
    interactor: FromDishka[DeleteProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Hard-delete the product. Allowed only while it is still in draft.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected delete command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ProductNotInDraftError: Product is no longer a draft —
            archive instead; HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )


@router.get(
    "/mine",
    summary="List or search products the current user can access",
    operation_id="getMyProducts",
    response_model=list[ProductSchema],
    responses={
        200: {
            "headers": {
                "x-total-count": {
                    "description": (
                        "Total number of accessible products matching "
                        "the filter (without pagination). Used by the "
                        "SPA to render numbered page controls — "
                        "`ceil(total / limit)` is the total page "
                        "count."
                    ),
                    "schema": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
    dependencies=_AUTH_SECURITY,
    error_map={**AUTHENTICATED_WITH_FIELD_MAP},
)
async def get_mine(
    request: Request,
    response: Response,
    list_interactor: FromDishka[GetMyProductsQueryHandler],
    search_interactor: FromDishka[SearchMyProductsQueryHandler],
    auth: FromDishka[Authenticator],
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
        description=(f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`)."),
        examples=[20],
    ),
    q: str | None = Query(
        None,
        min_length=SEARCH_QUERY_MIN_LEN,
        max_length=SEARCH_QUERY_MAX_LEN,
        description=(
            "Optional free-text search query. When omitted or empty, "
            "returns accessible products ordered by ``created_at`` "
            "descending (newest first). When provided, performs the "
            "same weighted full-text + ``pg_trgm`` fuzzy search used "
            "by the public catalog, restricted to the caller's "
            "accessible set (author OR active collaborator, any "
            "product status). Length bounds: "
            f"`[{SEARCH_QUERY_MIN_LEN}, {SEARCH_QUERY_MAX_LEN}]` "
            "(`SEARCH_QUERY_MIN_LEN` / `SEARCH_QUERY_MAX_LEN`)."
        ),
        examples=["python", "иванов", "машинное обучение"],
    ),
) -> list[ProductSchema]:
    """Return products accessible to the current user.

    A product appears in the result if the caller is its author or
    has an active collaboration on it (``PENDING_INVITE`` and
    ``REVOKED`` collaborations are excluded). Any product status is
    returned.

    Two modes share one URL — discriminated by the presence of ``q``:

    * **List mode** (``q`` omitted) — newest-first paginated set,
      identical to the legacy behaviour.
    * **Search mode** (``q`` provided) — weighted multi-field
      full-text search (name, author full name, tag names,
      HTML-stripped description) with a ``pg_trgm`` fuzzy fallback
      for typos and transliteration, restricted to the caller's
      accessible set.

    Args:
        request: Source of the access-token cookie.
        response: Injected FastAPI response so the handler can set
            the ``X-Total-Count`` header.
        list_interactor: Injected newest-first query handler.
        search_interactor: Injected free-text search query handler.
        auth: Injected authenticator that validates the access cookie.
        offset: Pagination offset.
        limit: Page size.
        q: Optional free-text query. When empty / omitted, list mode
            applies; otherwise search mode runs.

    Returns:
        List of :class:`ProductSchema` (body). In list mode ordered
        by ``created_at`` desc; in search mode ordered by combined
        ranking (``ts_rank_cd`` × 2 + ``similarity``) then
        ``created_at`` desc. The ``X-Total-Count`` response header
        carries the unpaginated match total so the SPA can drive
        numbered page controls without a second round-trip.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    pagination = Pagination(limit=limit, offset=offset)
    if q is None or not q.strip():
        result = await list_interactor.run(
            GetMyProductsQuery(
                user_id=ctx.user_id,
                pagination=pagination,
            ),
        )
    else:
        result = await search_interactor.run(
            SearchMyProductsQuery(
                user_id=ctx.user_id,
                q=q,
                pagination=pagination,
            ),
        )
    response.headers["X-Total-Count"] = str(result.total)
    return [ProductSchema.from_output(view) for view in result.items]


@router.get(
    "/name-availability",
    summary="Check whether a product name is available for the current user",
    operation_id="checkProductNameAvailability",
    response_model=ProductNameAvailabilitySchema,
    dependencies=_AUTH_SECURITY,
    error_map={**AUTHENTICATED_WITH_FIELD_MAP},
)
async def check_name_availability(
    request: Request,
    interactor: FromDishka[CheckProductNameAvailabilityQueryHandler],
    auth: FromDishka[Authenticator],
    name: str = Query(
        description=(
            "Candidate product name to test. Required, "
            f"non-empty, max length {TITLE_MAX_LEN} chars "
            "(`TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=TITLE_MAX_LEN,
        examples=["Async Python"],
    ),
) -> ProductNameAvailabilitySchema:
    """Pre-flight check whether the current user may use ``name``.

    A ``true`` response is informational, not a reservation —
    another request from the same user could grab the name in
    between. The authoritative check happens at create / rename
    time and surfaces ``ProductNameAlreadyTakenError`` (HTTP 409).
    Comparison is case-sensitive and includes archived products.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected check-name-availability query handler.
        auth: Injected authenticator that validates the access cookie.
        name: Candidate product name to test.

    Returns:
        :class:`ProductNameAvailabilitySchema` with ``available``
        set to ``true`` when the current user does not yet own a
        product with this name.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        FieldError: Schema constraints violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    result = await interactor.run(
        CheckProductNameAvailabilityQuery(
            author_id=ctx.user_id,
            name=name,
        ),
    )
    return ProductNameAvailabilitySchema(available=result.available)


@router.get(
    "",
    summary="List or search published products (public catalog)",
    operation_id="getPublishedProducts",
    response_model=list[ProductSchema],
    responses={
        200: {
            "headers": {
                "x-total-count": {
                    "description": (
                        "Total number of products matching the filter "
                        "(without pagination). Used by the SPA to "
                        "render numbered page controls — "
                        "`ceil(total / limit)` is the total page "
                        "count."
                    ),
                    "schema": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
)
async def get_published(
    response: Response,
    list_interactor: FromDishka[GetPublishedProductsQueryHandler],
    search_interactor: FromDishka[
        SearchPublishedProductsQueryHandler
    ],
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
        description=(f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`)."),
        examples=[20],
    ),
    q: str | None = Query(
        None,
        min_length=SEARCH_QUERY_MIN_LEN,
        max_length=SEARCH_QUERY_MAX_LEN,
        description=(
            "Optional free-text search query. When omitted or empty, "
            "returns published products ordered by ``created_at`` "
            "descending (newest first). When provided, performs a "
            "weighted full-text + fuzzy search across product name "
            "(weight A), author full name (B), attached tag names "
            "(B), and HTML-stripped description (C), ranked by "
            "``ts_rank_cd`` blended with ``pg_trgm`` similarity "
            "(typo-tolerant). Length bounds: "
            f"`[{SEARCH_QUERY_MIN_LEN}, {SEARCH_QUERY_MAX_LEN}]` "
            "(`SEARCH_QUERY_MIN_LEN` / `SEARCH_QUERY_MAX_LEN`)."
        ),
        examples=["python", "иванов", "машинное обучение"],
    ),
    tag_ids: list[UUID] = Query(
        default_factory=list,
        max_length=PRODUCT_TAGS_MAX,
        description=(
            "Optional tag filter. Repeat the parameter once per tag "
            "(`?tag_ids=<uuid>&tag_ids=<uuid>`). When one or more are "
            "supplied, the catalog is restricted to products carrying "
            "**every** listed tag (AND semantics) — pagination and the "
            "``X-Total-Count`` header are computed over the filtered "
            "set, not the full catalog. Composes with ``q`` (search "
            "intersected with the tag filter). Capped at "
            f"{PRODUCT_TAGS_MAX} ids (`PRODUCT_TAGS_MAX`, the "
            "per-product tag limit) — more can never match."
        ),
        examples=[["3fa85f64-5717-4562-b3fc-2c963f66afa6"]],
    ),
) -> list[ProductSchema]:
    """Return the public catalog of published products.

    Two modes share one URL — discriminated by the presence of ``q``:

    * **List mode** (``q`` omitted) — newest-first paginated catalog,
      identical to the legacy behaviour.
    * **Search mode** (``q`` provided) — weighted multi-field
      full-text search (name, author full name, tag names,
      HTML-stripped description) with a ``pg_trgm`` fuzzy fallback
      for typos and transliteration. Search is morphology-aware via
      the Russian text-search dictionary ("курсы" matches "курс").

    The optional ``tag_ids`` filter layers on top of **either** mode
    (AND across the listed tags), so the SPA's tag chips narrow both
    the plain catalog and a search; pagination and ``X-Total-Count``
    are always computed over the filtered result set.

    Args:
        response: Injected FastAPI response so the handler can set
            the ``X-Total-Count`` header.
        list_interactor: Injected newest-first query handler.
        search_interactor: Injected full-text search query handler.
        offset: Pagination offset.
        limit: Page size.
        q: Optional free-text query. When empty / omitted, list mode
            applies; otherwise search mode runs.
        tag_ids: Optional repeatable tag filter. When non-empty, both
            modes are restricted to products carrying every listed
            tag (AND); capped at ``PRODUCT_TAGS_MAX``. Composes with
            ``q``.

    Returns:
        List of :class:`ProductSchema` (body). In list mode ordered
        by ``created_at`` desc; in search mode ordered by combined
        ranking (``ts_rank_cd`` × 2 + ``similarity``) then
        ``created_at`` desc. The ``X-Total-Count`` response header
        carries the unpaginated match total so the SPA can drive
        numbered page controls without a second round-trip.
    """
    pagination = Pagination(limit=limit, offset=offset)
    tags = tuple(TagID(tag_id) for tag_id in tag_ids)
    if q is None or not q.strip():
        result = await list_interactor.run(
            GetPublishedProductsQuery(
                pagination=pagination, tag_ids=tags,
            ),
        )
    else:
        result = await search_interactor.run(
            SearchPublishedProductsQuery(
                q=q, pagination=pagination, tag_ids=tags,
            ),
        )
    response.headers["X-Total-Count"] = str(result.total)
    return [ProductSchema.from_output(view) for view in result.items]


@router.get(
    "/{product_id}",
    summary="Get a single product",
    operation_id="getProductById",
    response_model=ProductSchema,
    dependencies=_AUTH_SECURITY,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_one(
    request: Request,
    interactor: FromDishka[GetProductQueryHandler],
    auth: FromDishka[Authenticator],
    stats: FromDishka[StatisticsCollector],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Return a single product by id (public).

    Authentication is **optional**: anonymous callers receive the
    same payload as signed-in ones, regardless of the product's
    visibility — a ``PRIVATE`` product is still publicly browsable.
    Privacy only affects enrollment: self-enroll is refused for
    private products (see ``POST /products/{id}/enrollments``), and
    the ``visibility`` field lets the SPA hide the self-enroll CTA
    and show "invite-only" instead. A valid access cookie has one
    extra effect — the call records a ``product_view`` statistic
    attributed to the caller. Authors viewing their own products
    are **not** filtered out: a self-view is a valid analytics
    signal (preview / dashboard navigation) and the SPA can split it
    out later via ``actor_id == product.author_id``. A missing or
    stale cookie degrades silently to the anonymous path.

    Args:
        request: Source of the (optional) access cookie and
            ``Referer`` header used for the stat row.
        interactor: Injected get-product query handler.
        auth: Injected authenticator; consulted via
            :meth:`Authenticator.authenticate_optional`.
        stats: Injected statistics collector; failures are
            swallowed by the collector implementation.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        :class:`ProductSchema` with full product metadata, including
        nested author projection and webinar defaults when
        applicable.

    Raises:
        EntityNotFoundError: No product with the given id; HTTP 404.
    """
    target_id = ProductID(product_id)
    view = await interactor.run(GetProductQuery(oid=target_id))
    ctx = await auth.authenticate_optional(request)
    if ctx is not None:
        await stats.record(
            Statistic.for_product_view(
                actor_id=ctx.user_id,
                product_id=target_id,
                referrer=request.headers.get("referer"),
            ),
        )
    return ProductSchema.from_output(view)


# ============================== Q&A schemas ============================ #


class AddProductQASchema(BaseModel):
    """Body for ``POST /products/{product_id}/qa``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "Will I get a certificate?",
                    "answer": "Yes — once all sessions are completed.",
                    "position": 0,
                },
            ],
        },
    )

    question: str = Field(
        description=(
            f"Q&A question. Max length is {QA_QUESTION_MAX_LEN} chars "
            "(`QA_QUESTION_MAX_LEN`)."
        ),
        min_length=1,
        max_length=QA_QUESTION_MAX_LEN,
        examples=["Will I get a certificate?"],
    )
    answer: str = Field(
        description=(
            f"Q&A answer. Max length is {QA_ANSWER_MAX_LEN} chars "
            "(`QA_ANSWER_MAX_LEN`)."
        ),
        min_length=1,
        max_length=QA_ANSWER_MAX_LEN,
        examples=["Yes — once all sessions are completed."],
    )
    position: int = Field(
        description=(
            "Sort order within the product's Q&A list, `>= 0`. "
            "Reorder later via "
            "`PATCH /products/{product_id}/qa/{qa_id}/position`."
        ),
        ge=0,
        examples=[0],
    )


class ChangeProductQAQuestionSchema(BaseModel):
    """Body for ``PATCH /products/{product_id}/qa/{qa_id}/question``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": "How long is access?"}]},
    )

    value: str = Field(
        min_length=1,
        max_length=QA_QUESTION_MAX_LEN,
        description=(f"New question text. Max length {QA_QUESTION_MAX_LEN}."),
        examples=["How long is access?"],
    )


class ChangeProductQAAnswerSchema(BaseModel):
    """Body for ``PATCH /products/{product_id}/qa/{qa_id}/answer``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": "Lifetime access after purchase."}],
        },
    )

    value: str = Field(
        min_length=1,
        max_length=QA_ANSWER_MAX_LEN,
        description=(f"New answer text. Max length {QA_ANSWER_MAX_LEN}."),
        examples=["Lifetime access after purchase."],
    )


class ReorderProductQASchema(BaseModel):
    """Body for ``PATCH /products/{product_id}/qa/{qa_id}/position``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"position": 2}]},
    )

    position: int = Field(
        ge=0,
        description=("New sort position within the product's Q&A list, `>= 0`."),
        examples=[2],
    )


class ProductQASchema(BaseModel):
    """Q&A entry response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "5b2c8a90-6fcd-4d2c-9d11-9d4f0a44b6c8",
                    "product_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "question": "Will I get a certificate?",
                    "answer": "Yes — once all sessions are completed.",
                    "position": 0,
                },
            ],
        },
    )

    oid: UUID
    product_id: UUID
    question: str
    answer: str
    position: int

    @classmethod
    def from_view(cls, view: ProductQAView) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            question=view.question,
            answer=view.answer,
            position=view.position,
        )


class CreatedProductQASchema(BaseModel):
    """Response for ``POST /products/{product_id}/qa``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "5b2c8a90-6fcd-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created Q&A entry.",
        examples=["5b2c8a90-6fcd-4d2c-9d11-9d4f0a44b6c8"],
    )


# ============================== Q&A routes ============================= #


@router.post(
    "/{product_id}/qa",
    summary="Add a Q&A entry to a product",
    operation_id="addProductQA",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedProductQASchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_qa(
    request: Request,
    payload: AddProductQASchema,
    interactor: FromDishka[AddProductQACommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedProductQASchema:
    """Add a new Q&A entry to a product owned by the current user.

    Args:
        request: Source of the access-token cookie.
        payload: Q&A fields validated by ``AddProductQASchema``.
        interactor: Injected add-Q&A command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the new Q&A entry's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ResourceLimitReachedError: The product already has
            ``PRODUCT_QA_LIMIT`` Q&A entries; HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    qa_id = await interactor.run(
        AddProductQACommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            question=payload.question,
            answer=payload.answer,
            position=payload.position,
        ),
    )
    return CreatedProductQASchema(oid=qa_id)


@router.get(
    "/{product_id}/qa",
    summary="List a product's Q&A entries",
    operation_id="getProductQAList",
    response_model=list[ProductQASchema],
)
async def get_qa_list(
    interactor: FromDishka[GetProductQAListQueryHandler],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> list[ProductQASchema]:
    """Return Q&A entries attached to a product (public), by ascending position.

    Args:
        interactor: Injected list-Q&A query handler.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        List of :class:`ProductQASchema`, ordered by ``position``
        ascending. Returns an empty list when the product has no
        Q&A or doesn't exist (this is a list endpoint — readers
        only see content authored explicitly).
    """
    views = await interactor.run(
        GetProductQAListQuery(product_id=ProductID(product_id)),
    )
    return [ProductQASchema.from_view(view) for view in views]


# ======================= Enrollment routes ============================ #


class CreatedEnrollmentSchema(BaseModel):
    """Response for ``POST /products/{product_id}/enrollments``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created enrollment.",
        examples=["e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8"],
    )


@router.post(
    "/{product_id}/enrollments",
    summary="Self-enroll the current user into a product",
    operation_id="enrollIntoProduct",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedEnrollmentSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {
        CannotEnrollInUnpublishedProductError: (
            CANNOT_ENROLL_IN_UNPUBLISHED_PRODUCT_RULE
        ),
        CannotEnrollInPrivateProductError: (
            CANNOT_ENROLL_IN_PRIVATE_PRODUCT_RULE
        ),
        CannotEnrollInUnreleasedNoteError: (
            CANNOT_ENROLL_IN_UNRELEASED_NOTE_RULE
        ),
        ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE,
        AlreadyEnrolledError: ALREADY_ENROLLED_RULE,
    },
)
async def enroll_into_product(
    request: Request,
    interactor: FromDishka[EnrollIntoProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedEnrollmentSchema:
    """Create an enrollment for the current user in ``product_id``.

    The single public self-enroll entry point — replaces the legacy
    note-scoped path. Accepts any product type that advertises
    student enrollment (today: ``note`` only). The product must
    already be ``PUBLISHED``; drafts and archived products refuse
    with 409 ``CannotEnrollInUnpublishedProduct``. Admin grants
    (internal-only) go through a different handler and may target
    any status.

    Args:
        request: Source of the access-token cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with :class:`CreatedEnrollmentSchema`
        carrying the new enrollment's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: No product with the given id; HTTP 404.
        CannotEnrollInUnpublishedProductError: Product status is
            not ``PUBLISHED``; HTTP 409 with body carrying the
            offending status.
        CannotEnrollInPrivateProductError: Product visibility is
            ``PRIVATE`` (invite-only); HTTP 409. Access is only
            granted through an accepted gift/invite.
        CannotEnrollInUnreleasedNoteError: Product is a note
            with no releases yet; HTTP 409.
        ProductDoesNotSupportError: Product type does not advertise
            ``HAS_NOTE_ENROLLMENT``; HTTP 409.
        AlreadyEnrolledError: Caller already has an enrollment in
            this product; HTTP 409.
    """
    ctx = await auth.authenticate(request)
    enrollment_id = await interactor.run(
        EnrollIntoProductCommand(
            student_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    return CreatedEnrollmentSchema(oid=enrollment_id)


# ===================== Note-enrollment routes ======================== #


@note_router.get(
    "/{note_id}/enrollments",
    summary="List a note's enrollments",
    operation_id="getNoteEnrollments",
    response_model=list[EnrollmentSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def get_note_enrollments(
    request: Request,
    interactor: FromDishka[GetProductEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: UUID = _NOTE_ID_PATH,
) -> list[EnrollmentSchema]:
    """Return note enrollments.

    Caller needs ``READ_PRODUCT`` on the product (owner or any
    collaborator with that permission). Returns the unified
    :class:`EnrollmentSchema`; ``type`` is always ``"note"``
    for this endpoint.

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller has no
            collaboration with ``READ_PRODUCT``.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetProductEnrollmentsQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(note_id),
        ),
    )
    return [EnrollmentSchema.from_view(v) for v in views]


# ---------------------------- recommendations ------------------------- #


@me_router.get(
    "/recommended-products",
    summary="Get products recommended for the current user",
    operation_id="getMyRecommendedProducts",
    response_model=list[ProductSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def get_my_recommended_products(
    request: Request,
    interactor: FromDishka[RecommendForMeQueryHandler],
    auth: FromDishka[Authenticator],
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
        description=(f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`)."),
        examples=[20],
    ),
) -> list[ProductSchema]:
    """Return published products ranked for the authenticated user.

    Ranking blends four signals (tag affinity, author affinity,
    recent popularity, freshness) configured by
    ``RECOMMENDATIONS_WEIGHT_*`` env vars. Products the user owns
    or is already actively/completed enrolled in are excluded
    server-side. ``REFUNDED`` enrollments do not exclude — similar
    offers stay relevant.

    Cold start (no enrollment history) collapses to
    ``popularity + freshness``, returning a "top of the platform"
    list rather than an empty response.

    Args:
        offset: Pagination offset.
        limit: Page size.

    Returns:
        List of :class:`ProductSchema`, ordered by descending
        recommendation score (re-ranked in the handler, not on the
        DB). Same projection as ``GET /products`` so existing SPA
        product cards render unchanged.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    outputs = await interactor.run(
        RecommendForMeQuery(
            user_id=ctx.user_id,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [ProductSchema.from_output(view) for view in outputs]
