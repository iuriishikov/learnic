from datetime import date, datetime
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
    UploadFile,
    status,
)
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.cohort.add import (
    AddCohortCommand,
    AddCohortCommandHandler,
)
from learnic.application.commands.course_enrollment.enroll import (
    EnrollStudentInCourseCommand,
    EnrollStudentInCourseCommandHandler,
)
from learnic.application.commands.product.add_course import (
    AddCourseProductCommand,
    AddCourseProductCommandHandler,
)
from learnic.application.commands.product.add_webinar import (
    AddWebinarProductCommand,
    AddWebinarProductCommandHandler,
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
from learnic.application.commands.product.update_webinar_defaults import (
    UpdateWebinarDefaultsCommand,
    UpdateWebinarDefaultsCommandHandler,
)
from learnic.application.commands.product_qa.add import (
    AddProductQACommand,
    AddProductQACommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInUnreleasedCourseError,
    CannotPublishCourseDirectlyError,
    EntityNotFoundError,
    ProductNameAlreadyTakenError,
    ProductNotArchivedError,
    ProductNotInDraftError,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentView,
)
from learnic.application.queries.course_enrollment.list_for_product import (
    GetProductCourseEnrollmentsQuery,
    GetProductCourseEnrollmentsQueryHandler,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.common.persistence.product import (
    WebinarDetailsView,
)
from learnic.application.common.persistence.cohort import CohortView
from learnic.application.common.persistence.product_qa import ProductQAView
from learnic.application.queries.cohort.get_for_webinar import (
    GetWebinarCohortsQuery,
    GetWebinarCohortsQueryHandler,
)
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
from learnic.application.queries.product_qa.list import (
    GetProductQAListQuery,
    GetProductQAListQueryHandler,
)
from learnic.entities.cohort.constants import COHORT_NAME_MAX_LEN
from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
)
from learnic.entities.product.constants import (
    DESCRIPTION_MAX_LEN,
    DURATION_HOURS_MAX,
    DURATION_HOURS_MIN,
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    STREAM_URL_MAX_LEN,
    TITLE_MAX_LEN,
    WEBINAR_DURATION_MINUTES_MAX,
    WEBINAR_DURATION_MINUTES_MIN,
    WEBINAR_LESSONS_MAX,
    WEBINAR_LESSONS_MIN,
    WEBINAR_PARTICIPANTS_MIN,
)
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    ALREADY_ENROLLED_RULE,
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    CANNOT_ENROLL_IN_UNRELEASED_COURSE_RULE,
    CANNOT_PUBLISH_COURSE_DIRECTLY_RULE,
    ENTITY_NOT_FOUND_RULE,
    PRODUCT_DOES_NOT_SUPPORT_RULE,
    PRODUCT_NAME_TAKEN_RULE,
    PRODUCT_NOT_ARCHIVED_RULE,
    PRODUCT_NOT_IN_DRAFT_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import FileSchema, UserRefSchema
from learnic.presentation.http.common.uploads import read_image_upload

router = ErrorAwareRouter(
    prefix="/products",
    tags=["Products"],
    route_class=DishkaErrorAwareRoute,
)

# Course-enrollment endpoints live under /courses (parallel to other
# course-specific routers in course_content.py / course_release.py).
# Listed here for code locality with the rest of product.py — these
# operations still take a ``ProductID`` underneath but the URL surface
# is course-scoped.
course_router = ErrorAwareRouter(
    prefix="/courses",
    tags=["CourseEnrollments"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_COURSE_ID_PATH: Final = Path(
    description="Target course product's UUID.",
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


# ---------------------------- response schemas ------------------------- #


class WebinarDetailsSchema(BaseModel):
    """Webinar-specific defaults projection (response only)."""

    total_lessons: int = Field(examples=[8])
    default_duration_minutes: int = Field(examples=[90])
    allow_recording: bool = Field(examples=[True])
    default_max_participants: int | None = Field(examples=[50, None])
    default_stream_url: str | None = Field(
        examples=["https://meet.example.com/sql", None],
    )
    access_window_minutes: int | None = Field(examples=[15, None])

    @classmethod
    def from_view(cls, view: WebinarDetailsView) -> Self:
        return cls(
            total_lessons=view.total_lessons,
            default_duration_minutes=view.default_duration_minutes,
            allow_recording=view.allow_recording,
            default_max_participants=view.default_max_participants,
            default_stream_url=view.default_stream_url,
            access_window_minutes=view.access_window_minutes,
        )


class ProductSchema(BaseModel):
    """Full product projection returned by ``GET /products/...``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "type": "course",
                    "status": "published",
                    "name": "Async Python deep dive",
                    "description": "<p>A 30-hour course.</p>",
                    "total_duration_in_hours": 30,
                    "author": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "full_name": "Lovelace Ada",
                        "email": "a*****a@example.com",
                    },
                    "webinar_details": None,
                    "cover_url": (
                        "https://s3.example.com/products/cover.png"
                        "?X-Amz-Signature=..."
                    ),
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
    name: str
    description: str | None
    total_duration_in_hours: int | None
    author: UserRefSchema
    webinar_details: WebinarDetailsSchema | None
    cover_url: str | None = Field(
        default=None,
        description=(
            "Short-lived presigned URL for the product's cover image, "
            "or `null` when no cover is attached. The URL expires; "
            "re-fetch the product resource to get a fresh one."
        ),
        examples=[
            None,
            "https://s3.example.com/products/cover.png?X-Amz-Signature=...",
        ],
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
            name=view.name,
            description=view.description,
            total_duration_in_hours=view.total_duration_in_hours,
            author=UserRefSchema.from_view(view.author),
            webinar_details=(
                WebinarDetailsSchema.from_view(view.webinar_details)
                if view.webinar_details is not None
                else None
            ),
            cover_url=view.cover_url,
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
    "/courses",
    summary="Create a new course product",
    operation_id="addCourseProduct",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedProductSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {ProductNameAlreadyTakenError: PRODUCT_NAME_TAKEN_RULE},
)
async def add_course(
    request: Request,
    interactor: FromDishka[AddCourseProductCommandHandler],
    auth: FromDishka[Authenticator],
    name: _NameField,
    description_html: _DescriptionField = None,
    total_duration_in_hours: _DurationHoursField = None,
    cover: _CoverField = None,
) -> CreatedProductSchema:
    """Create a new course product owned by the current user.

    Only ``name`` is required — every other field is optional and
    can be filled in later via PATCH endpoints. The endpoint
    accepts ``multipart/form-data`` so the cover image can be
    attached in the same request as the metadata fields.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected add-course command handler.
        auth: Injected authenticator that validates the access cookie.
        name: Form field — product title (VO-validated). Required.
        description_html: Optional form field — HTML description
            (sanitized then VO-validated). Omit to leave empty.
        total_duration_in_hours: Optional form field — total duration
            in hours. Omit to leave unset.
        cover: Optional ``multipart/form-data`` file part. Capped at
            ``MAX_FILE_SIZE_BYTES``; the server reads ``Content-Type``
            from the upload.

    Returns:
        ``201 Created`` with the new product's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        ProductNameAlreadyTakenError: The current author already has
            a product with this name; HTTP 409.
        FieldError: Value-object invariants violated; HTTP 422.
        FileTooLargeError: Cover payload over ``MAX_FILE_SIZE_BYTES``;
            HTTP 422.
    """
    ctx = await auth.authenticate(request)
    cover_data, cover_content_type = await _read_optional_cover(cover)
    oid = await interactor.run(
        AddCourseProductCommand(
            author_id=ctx.user_id,
            name=name,
            description_html=description_html,
            total_duration_in_hours=total_duration_in_hours,
            cover=cover_data,
            cover_content_type=cover_content_type,
        ),
    )
    return CreatedProductSchema(oid=oid)


_TotalLessonsField = Annotated[
    int | None,
    Form(
        description=(
            "Optional total lessons per cohort, "
            f"`[{WEBINAR_LESSONS_MIN}, {WEBINAR_LESSONS_MAX}]`. "
            "Omit to fill in later via "
            "`PUT /products/{id}/webinar-defaults`."
        ),
        ge=WEBINAR_LESSONS_MIN,
        le=WEBINAR_LESSONS_MAX,
    ),
]
_DefaultDurationMinutesField = Annotated[
    int | None,
    Form(
        description=(
            "Optional default per-session duration in minutes, "
            f"`[{WEBINAR_DURATION_MINUTES_MIN}, "
            f"{WEBINAR_DURATION_MINUTES_MAX}]`. Omit to fill in "
            "later via `PUT /products/{id}/webinar-defaults`."
        ),
        ge=WEBINAR_DURATION_MINUTES_MIN,
        le=WEBINAR_DURATION_MINUTES_MAX,
    ),
]
_AllowRecordingField = Annotated[
    bool | None,
    Form(
        description=(
            "Optional — whether sessions may be recorded by default. "
            "Omit to fill in later via "
            "`PUT /products/{id}/webinar-defaults`."
        ),
    ),
]
_DefaultMaxParticipantsField = Annotated[
    int | None,
    Form(
        description=(
            f"Default participants cap (≥ {WEBINAR_PARTICIPANTS_MIN}); omit for no cap."
        ),
        ge=WEBINAR_PARTICIPANTS_MIN,
    ),
]
_DefaultStreamUrlField = Annotated[
    str | None,
    Form(
        description=(
            "Default streaming URL for cohorts of this webinar; "
            f"max length {STREAM_URL_MAX_LEN}. Omit if each cohort "
            "supplies its own."
        ),
        max_length=STREAM_URL_MAX_LEN,
    ),
]
_AccessWindowMinutesField = Annotated[
    int | None,
    Form(
        description=(
            "Minutes before a session students can join; omit to use "
            "the platform default."
        ),
        ge=0,
    ),
]


@router.post(
    "/webinars",
    summary="Create a new webinar product",
    operation_id="addWebinarProduct",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedProductSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {ProductNameAlreadyTakenError: PRODUCT_NAME_TAKEN_RULE},
)
async def add_webinar(
    request: Request,
    interactor: FromDishka[AddWebinarProductCommandHandler],
    auth: FromDishka[Authenticator],
    name: _NameField,
    description_html: _DescriptionField = None,
    total_duration_in_hours: _DurationHoursField = None,
    total_lessons: _TotalLessonsField = None,
    default_duration_minutes: _DefaultDurationMinutesField = None,
    allow_recording: _AllowRecordingField = None,
    default_max_participants: _DefaultMaxParticipantsField = None,
    default_stream_url: _DefaultStreamUrlField = None,
    access_window_minutes: _AccessWindowMinutesField = None,
    cover: _CoverField = None,
) -> CreatedProductSchema:
    """Create a new webinar product. Only ``name`` is required.

    Same ``multipart/form-data`` shape as ``POST /products/courses``,
    extended with optional webinar-default fields. Webinar defaults
    (``total_lessons``, ``default_duration_minutes``,
    ``allow_recording`` and the optional cohort settings) may be
    omitted; in that case the product is created without
    ``webinar_details`` and the author fills them in later via
    ``PUT /products/{id}/webinar-defaults``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected add-webinar command handler.
        auth: Injected authenticator that validates the access cookie.
        name: Form field — product title. Required.
        description_html: Optional form field — HTML description.
        total_duration_in_hours: Optional form field — total
            duration in hours.
        total_lessons: Optional form field — total lessons per cohort.
        default_duration_minutes: Optional form field — default
            per-session duration in minutes.
        allow_recording: Optional form field — whether sessions may
            be recorded by default.
        default_max_participants: Optional form field — default
            participants cap.
        default_stream_url: Optional form field — default streaming
            URL.
        access_window_minutes: Optional form field — access window
            in minutes before a session.
        cover: Optional ``multipart/form-data`` file part — cover
            image. Capped at ``MAX_FILE_SIZE_BYTES``.

    Returns:
        ``201 Created`` with the new product's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        ProductNameAlreadyTakenError: The current author already has
            a product with this name; HTTP 409.
        FieldError: Value-object invariants violated; HTTP 422.
        FileTooLargeError: Cover payload over ``MAX_FILE_SIZE_BYTES``;
            HTTP 422.
    """
    ctx = await auth.authenticate(request)
    cover_data, cover_content_type = await _read_optional_cover(cover)
    oid = await interactor.run(
        AddWebinarProductCommand(
            author_id=ctx.user_id,
            name=name,
            description_html=description_html,
            total_duration_in_hours=total_duration_in_hours,
            total_lessons=total_lessons,
            default_duration_minutes=default_duration_minutes,
            allow_recording=allow_recording,
            default_max_participants=default_max_participants,
            default_stream_url=default_stream_url,
            access_window_minutes=access_window_minutes,
            cover=cover_data,
            cover_content_type=cover_content_type,
        ),
    )
    return CreatedProductSchema(oid=oid)


async def _read_optional_cover(
    upload: UploadFile | None,
) -> tuple[bytes | None, str | None]:
    """Read an optional cover ``UploadFile`` to ``(bytes, content_type)``.

    Returns ``(None, None)`` when nothing was uploaded so the
    handler can skip the file-creation branch entirely.
    """
    if upload is None:
        return None, None
    data, content_type = await read_image_upload(upload)
    return data, content_type


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


@router.post(
    "/{product_id}/cover",
    summary="Upload (or replace) a product's cover image",
    operation_id="setProductCover",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=FileSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def set_cover(
    request: Request,
    file: UploadFile,
    interactor: FromDishka[SetProductCoverCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> FileSchema:
    """Upload (or replace) a product's cover image.

    The previous cover (if any) is soft-deleted in the same
    transaction; only the S3 PUT for the new blob happens
    out-of-band.

    Args:
        request: Source of the access-token cookie.
        file: ``multipart/form-data`` field ``file`` carrying the
            image bytes. Capped at ``MAX_FILE_SIZE_BYTES``; the server
            reads ``Content-Type`` from the upload and rejects
            payloads above the limit with a 422 ``FileTooLargeError``.
        interactor: Injected set-cover command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with :class:`FileSchema` carrying the new
        file's id.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        FieldError: Cover VO invariants violated; HTTP 422.
        FileTooLargeError: Payload over ``MAX_FILE_SIZE_BYTES``;
            HTTP 422.
    """
    ctx = await auth.authenticate(request)
    data, content_type = await read_image_upload(file)
    file_id = await interactor.run(
        SetProductCoverCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            data=data,
            content_type=content_type,
        ),
    )
    return FileSchema(oid=file_id)


@router.delete(
    "/{product_id}/cover",
    summary="Detach a product's cover image",
    operation_id="removeProductCover",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def remove_cover(
    request: Request,
    interactor: FromDishka[RemoveProductCoverCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Detach the product's cover and soft-delete the file row.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected remove-cover command handler.
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
        RemoveProductCoverCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )


@router.post(
    "/{product_id}/publish",
    summary="Publish a webinar product",
    operation_id="publishProduct",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {CannotPublishCourseDirectlyError: CANNOT_PUBLISH_COURSE_DIRECTLY_RULE},
)
async def publish(
    request: Request,
    interactor: FromDishka[PublishProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Mark a webinar product published. Idempotent on already-published.

    Course products cannot be published via this endpoint — they
    are published implicitly by creating their first release
    (``POST /products/{id}/releases``). Direct publish on a
    course returns HTTP 409 ``CannotPublishCourseDirectly``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected publish command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        CannotPublishCourseDirectlyError: Product is a course;
            HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        PublishProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )


@router.post(
    "/{product_id}/archive",
    summary="Archive a product",
    operation_id="archiveProduct",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def archive(
    request: Request,
    interactor: FromDishka[ArchiveProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Move the product into the archived state.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected archive command handler.
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
        ArchiveProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )


@router.post(
    "/{product_id}/unarchive",
    summary="Restore an archived product",
    operation_id="unarchiveProduct",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductNotArchivedError: PRODUCT_NOT_ARCHIVED_RULE},
)
async def unarchive(
    request: Request,
    interactor: FromDishka[UnarchiveProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Move an archived product back to its prior lifecycle state.

    The target status is derived from ``published_at``: a non-null
    value means the product was previously published (webinar via
    ``POST /products/{id}/publish``, course via its first release)
    and the product returns to ``published``; otherwise it returns
    to ``draft``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected unarchive command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

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
    summary="List products the current user can access",
    operation_id="getMyProducts",
    response_model=list[ProductSchema],
    dependencies=_AUTH_SECURITY,
    error_map={**AUTHENTICATED_WITH_FIELD_MAP},
)
async def get_mine(
    request: Request,
    interactor: FromDishka[GetMyProductsQueryHandler],
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
    """Return products accessible to the current user, newest first.

    A product appears in the result if the caller is its author or
    has an active collaboration on it (``PENDING_INVITE`` and
    ``REVOKED`` collaborations are excluded). Any product status is
    returned.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected get-my-products query handler.
        auth: Injected authenticator that validates the access cookie.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        List of :class:`ProductSchema`, ordered by ``created_at``
        descending.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetMyProductsQuery(
            user_id=ctx.user_id,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [ProductSchema.from_output(view) for view in views]


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
    summary="List published products (public catalog)",
    operation_id="getPublishedProducts",
    response_model=list[ProductSchema],
)
async def get_published(
    interactor: FromDishka[GetPublishedProductsQueryHandler],
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
    """Return all published products (public catalog), newest first.

    Args:
        interactor: Injected get-published-products query handler.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        List of :class:`ProductSchema`, ordered by ``created_at``
        descending.
    """
    views = await interactor.run(
        GetPublishedProductsQuery(
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [ProductSchema.from_output(view) for view in views]


@router.get(
    "/{product_id}",
    summary="Get a single product",
    operation_id="getProductById",
    response_model=ProductSchema,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_one(
    interactor: FromDishka[GetProductQueryHandler],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> ProductSchema:
    """Return a single product by id (public).

    Args:
        interactor: Injected get-product query handler.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        :class:`ProductSchema` with full product metadata, including
        nested author projection and webinar defaults when
        applicable.

    Raises:
        EntityNotFoundError: No product with the given id; HTTP 404.
    """
    view = await interactor.run(GetProductQuery(oid=ProductID(product_id)))
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


class UpdateWebinarDefaultsSchema(BaseModel):
    """Body for ``PUT /products/{product_id}/webinar-defaults``.

    PUT semantics — every webinar-default field is required and the
    current values are replaced atomically. To clear an optional
    field, send `null`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total_lessons": 10,
                    "default_duration_minutes": 90,
                    "allow_recording": True,
                    "default_max_participants": 30,
                    "default_stream_url": "https://meet.example.com/sql",
                    "access_window_minutes": 10,
                },
            ],
        },
    )

    total_lessons: int = Field(
        ge=WEBINAR_LESSONS_MIN,
        le=WEBINAR_LESSONS_MAX,
        description=(
            "Total lessons per cohort. Must be in "
            f"`[{WEBINAR_LESSONS_MIN}, {WEBINAR_LESSONS_MAX}]`."
        ),
        examples=[10],
    )
    default_duration_minutes: int = Field(
        ge=WEBINAR_DURATION_MINUTES_MIN,
        le=WEBINAR_DURATION_MINUTES_MAX,
        description=(
            "Default per-session duration. Must be in "
            f"`[{WEBINAR_DURATION_MINUTES_MIN}, "
            f"{WEBINAR_DURATION_MINUTES_MAX}]`."
        ),
        examples=[90],
    )
    allow_recording: bool = Field(
        description="Whether sessions may be recorded.",
        examples=[True],
    )
    default_max_participants: int | None = Field(
        ge=WEBINAR_PARTICIPANTS_MIN,
        description=(
            f"Default participants cap (≥ {WEBINAR_PARTICIPANTS_MIN}); "
            "`null` for no cap."
        ),
        examples=[30, None],
    )
    default_stream_url: str | None = Field(
        max_length=STREAM_URL_MAX_LEN,
        description=(
            "Default streaming URL; `null` if each cohort supplies "
            f"its own. Max length {STREAM_URL_MAX_LEN} chars."
        ),
        examples=["https://meet.example.com/sql", None],
    )
    access_window_minutes: int | None = Field(
        ge=0,
        description=(
            "Minutes before a session students can join; `null` for platform default."
        ),
        examples=[10, None],
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


@router.put(
    "/{product_id}/webinar-defaults",
    summary="Replace a webinar product's default cohort settings",
    operation_id="updateWebinarDefaults",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE},
)
async def update_webinar_defaults(
    request: Request,
    payload: UpdateWebinarDefaultsSchema,
    interactor: FromDishka[UpdateWebinarDefaultsCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Replace all webinar-default settings on a webinar product.

    PUT semantics — every field is required, current values are
    replaced atomically.

    Args:
        request: Source of the access-token cookie.
        payload: Full webinar-defaults payload.
        interactor: Injected update-defaults command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Target product's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ProductDoesNotSupportError: Product is a course, not a webinar;
            HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateWebinarDefaultsCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            total_lessons=payload.total_lessons,
            default_duration_minutes=payload.default_duration_minutes,
            allow_recording=payload.allow_recording,
            default_max_participants=payload.default_max_participants,
            default_stream_url=payload.default_stream_url,
            access_window_minutes=payload.access_window_minutes,
        ),
    )


# ============================ Cohort schemas =========================== #


class AddCohortSchema(BaseModel):
    """Body for ``POST /products/{product_id}/cohorts``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "host_id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Поток №3, осень 2026",
                    "max_participants": 30,
                    "starts_on": "2026-09-01",
                    "ends_on": "2026-12-15",
                },
            ],
        },
    )

    host_id: UUID = Field(
        description=(
            "UUID of the user who will host the cohort's sessions. "
            "Authorisation to host is enforced in business logic."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    name: str | None = Field(
        default=None,
        description=(
            'Human-readable cohort name (e.g. "Поток №3, осень 2026"). '
            f"Max length {COHORT_NAME_MAX_LEN} chars "
            "(`COHORT_NAME_MAX_LEN`); `null` to leave unnamed."
        ),
        max_length=COHORT_NAME_MAX_LEN,
        examples=["Поток №3, осень 2026", None],
    )
    max_participants: int | None = Field(
        default=None,
        description=(
            f"Cohort-level cap (≥ {WEBINAR_PARTICIPANTS_MIN}); "
            "`null` falls back to the webinar's "
            "`default_max_participants`."
        ),
        ge=WEBINAR_PARTICIPANTS_MIN,
        examples=[30, None],
    )
    starts_on: date = Field(
        description="Cohort start date (inclusive).",
        examples=["2026-09-01"],
    )
    ends_on: date | None = Field(
        default=None,
        description="Cohort end date (inclusive); `null` = open-ended.",
        examples=["2026-12-15", None],
    )


class CreatedCohortSchema(BaseModel):
    """Response for ``POST /products/{product_id}/cohorts``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created cohort.",
        examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
    )


class CohortListItemSchema(BaseModel):
    """Cohort projection returned by list endpoints under products."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8",
                    "webinar_id": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "host_id": ("550e8400-e29b-41d4-a716-446655440000"),
                    "name": "Поток №3, осень 2026",
                    "max_participants": 30,
                    "starts_on": "2026-09-01",
                    "ends_on": "2026-12-15",
                    "enrollment_status": "open",
                    "lifecycle_status": "upcoming",
                    "created_at": "2026-04-29T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID
    webinar_id: UUID
    host_id: UUID
    name: str | None
    max_participants: int | None
    starts_on: date
    ends_on: date | None
    enrollment_status: CohortEnrollmentStatus
    lifecycle_status: CohortLifecycleStatus
    created_at: datetime

    @classmethod
    def from_view(cls, view: CohortView) -> Self:
        return cls(
            oid=view.oid,
            webinar_id=view.webinar_id,
            host_id=view.host_id,
            name=view.name,
            max_participants=view.max_participants,
            starts_on=view.starts_on,
            ends_on=view.ends_on,
            enrollment_status=view.enrollment_status,
            lifecycle_status=view.lifecycle_status,
            created_at=view.created_at,
        )


# ============================ Cohort routes ============================ #


@router.post(
    "/{product_id}/cohorts",
    summary="Create a new cohort under a webinar product",
    operation_id="addCohort",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedCohortSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE},
)
async def add_cohort(
    request: Request,
    payload: AddCohortSchema,
    interactor: FromDishka[AddCohortCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedCohortSchema:
    """Create a new cohort under a webinar product owned by the caller.

    Args:
        request: Source of the access-token cookie.
        payload: Cohort fields validated by ``AddCohortSchema``.
        interactor: Injected add-cohort command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Parent webinar product's UUID, parsed from path.

    Returns:
        ``201 Created`` with the new cohort's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the product's author;
            HTTP 403.
        EntityNotFoundError: No product with the given id; HTTP 404.
        ProductDoesNotSupportError: Product is a course; HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    cohort_id = await interactor.run(
        AddCohortCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            host_id=UserID(payload.host_id),
            starts_on=payload.starts_on,
            name=payload.name,
            max_participants=payload.max_participants,
            ends_on=payload.ends_on,
        ),
    )
    return CreatedCohortSchema(oid=cohort_id)


@router.get(
    "/{product_id}/cohorts",
    summary="List a webinar product's cohorts (public)",
    operation_id="getWebinarCohorts",
    response_model=list[CohortListItemSchema],
)
async def get_cohorts(
    interactor: FromDishka[GetWebinarCohortsQueryHandler],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> list[CohortListItemSchema]:
    """Return cohorts attached to a webinar product, by ascending start date.

    Args:
        interactor: Injected list-cohorts query handler.
        product_id: Parent product's UUID, parsed from the URL path.

    Returns:
        List of :class:`CohortListItemSchema`. Empty list when the
        product has no cohorts (or doesn't exist) — the catalog is
        public so no 404 is raised here.
    """
    views = await interactor.run(
        GetWebinarCohortsQuery(webinar_id=ProductID(product_id)),
    )
    return [CohortListItemSchema.from_view(view) for view in views]


# ===================== Course-enrollment schemas ======================= #


class CreatedCourseEnrollmentSchema(BaseModel):
    """Response for ``POST /courses/{course_id}/enrollments``."""

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


class CourseEnrollmentListItemSchema(BaseModel):
    """Course enrollment projection in ``GET /courses/{course_id}/enrollments``."""

    oid: UUID
    product_id: UUID
    student_id: UUID
    status: CourseEnrollmentStatus
    progress_percent: int
    enrolled_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_view(cls, view: CourseEnrollmentView) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            student_id=view.student_id,
            status=view.status,
            progress_percent=view.progress_percent,
            enrolled_at=view.enrolled_at,
            completed_at=view.completed_at,
        )


# ===================== Course-enrollment routes ======================== #


@course_router.post(
    "/{course_id}/enrollments",
    summary="Enroll the current user into a course",
    operation_id="enrollIntoCourse",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedCourseEnrollmentSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {
        ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE,
        AlreadyEnrolledError: ALREADY_ENROLLED_RULE,
        CannotEnrollInUnreleasedCourseError: (CANNOT_ENROLL_IN_UNRELEASED_COURSE_RULE),
    },
)
async def enroll_in_course(
    request: Request,
    interactor: FromDishka[EnrollStudentInCourseCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,
) -> CreatedCourseEnrollmentSchema:
    """Self-enroll the current user into a course product.

    The course must already have at least one release; otherwise
    HTTP 409 ``CannotEnrollInUnreleasedCourse``. The enrollment
    captures the latest release id at signup time (strict
    pinning).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected enroll command handler.
        auth: Injected authenticator that validates the access cookie.
        course_id: Target course UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the new enrollment's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        EntityNotFoundError: HTTP 404.
        ProductDoesNotSupportError: Product is a webinar, not a course;
            HTTP 409.
        AlreadyEnrolledError: HTTP 409.
        CannotEnrollInUnreleasedCourseError: Course has no
            releases yet; HTTP 409.
    """
    ctx = await auth.authenticate(request)
    enrollment_id = await interactor.run(
        EnrollStudentInCourseCommand(
            student_id=ctx.user_id,
            product_id=ProductID(course_id),
        ),
    )
    return CreatedCourseEnrollmentSchema(oid=enrollment_id)


@course_router.get(
    "/{course_id}/enrollments",
    summary="List a course's enrollments",
    operation_id="getCourseEnrollments",
    response_model=list[CourseEnrollmentListItemSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def get_course_enrollments(
    request: Request,
    interactor: FromDishka[GetProductCourseEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,
) -> list[CourseEnrollmentListItemSchema]:
    """Return course enrollments.

    Caller needs ``READ_PRODUCT`` on the product (owner or any
    collaborator with that permission).

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller has no
            collaboration with ``READ_PRODUCT``.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetProductCourseEnrollmentsQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
        ),
    )
    return [CourseEnrollmentListItemSchema.from_view(v) for v in views]
