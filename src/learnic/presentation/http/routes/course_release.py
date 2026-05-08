from datetime import datetime
from typing import Annotated, Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.course_release.create import (
    CreateCourseReleaseCommand,
    CreateCourseReleaseCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    NotACourseError,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
    CourseReleaseSummaryView,
    ReleaseLessonView,
    ReleaseModuleView,
)
from learnic.application.queries.course_content.get_for_student import (
    GetMyCourseContentQuery,
    GetMyCourseContentQueryHandler,
)
from learnic.application.queries.course_release.get_content import (
    GetCourseReleaseContentQuery,
    GetCourseReleaseContentQueryHandler,
)
from learnic.application.queries.course_release.list_for_product import (
    ListCourseReleasesQuery,
    ListCourseReleasesQueryHandler,
)
from learnic.entities.course_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.product.ids import ProductID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    AUTHENTICATED_OWNER_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
    NOT_A_COURSE_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.routes.course_content import (
    CourseDraftLessonSchema,
    CourseDraftModuleSchema,
    _block_view_to_schema,
)

router = ErrorAwareRouter(
    prefix="/courses",
    tags=["CourseReleases"],
    route_class=DishkaErrorAwareRoute,
)

# Student-facing read endpoint lives under the CourseContent tag
# (it returns release content but from the *student's* enrollment
# perspective, parallel to the author-side draft tree).
student_router = ErrorAwareRouter(
    prefix="/courses",
    tags=["CourseContent"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COURSE_ID_PATH: Final = Path(
    description="Target course product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_RELEASE_ID_PATH: Final = Path(
    description="Target release UUID.",
    examples=["7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"],
)

_COURSE_AUTHOR_MAP = AUTHENTICATED_OWNER_FIELD_MAP | {
    NotACourseError: NOT_A_COURSE_RULE,
}


# ============================== schemas ============================== #


class CreateCourseReleaseSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/releases``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "kind": "minor",
                    "notes": "Added a new module on asyncio internals.",
                },
            ],
        },
    )

    kind: CourseReleaseKind = Field(
        description=(
            "Semver bump kind. From ``v(M.m.p)``: `patch` → "
            "`v(M.m.p+1)`, `minor` → `v(M.m+1.0)`, `major` → "
            "`v(M+1.0.0)`. First release starts from baseline "
            "``v0.0.0`` so `patch` → `v0.0.1`, etc."
        ),
        examples=[CourseReleaseKind.MINOR],
    )
    notes: str | None = Field(
        default=None,
        description=(
            f"Optional release notes. Max length "
            f"{RELEASE_NOTES_MAX_LEN} chars (`RELEASE_NOTES_MAX_LEN`)."
        ),
        min_length=1,
        max_length=RELEASE_NOTES_MAX_LEN,
        examples=["Added a new module on asyncio internals.", None],
    )


class CourseReleaseVersionSchema(BaseModel):
    """Semver triplet for a release."""

    major: int = Field(examples=[1])
    minor: int = Field(examples=[0])
    patch: int = Field(examples=[0])


class CourseReleaseSummarySchema(BaseModel):
    """Lightweight release info — list element + create response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d",
                    "ordinal": 3,
                    "version": {"major": 1, "minor": 1, "patch": 0},
                    "kind": "minor",
                    "notes": "Added a new module on asyncio internals.",
                    "released_at": "2026-05-01T10:00:00+00:00",
                    "released_by": "550e8400-e29b-41d4-a716-446655440000",
                },
            ],
        },
    )

    oid: UUID
    ordinal: int
    version: CourseReleaseVersionSchema
    kind: CourseReleaseKind
    notes: str | None
    released_at: datetime
    released_by: UUID

    @classmethod
    def from_view(cls, view: CourseReleaseSummaryView) -> Self:
        return cls(
            oid=view.oid,
            ordinal=view.ordinal,
            version=CourseReleaseVersionSchema(
                major=view.major,
                minor=view.minor,
                patch=view.patch,
            ),
            kind=view.kind,
            notes=view.notes,
            released_at=view.released_at,
            released_by=view.released_by,
        )

    @classmethod
    def from_entity(cls, release: CourseRelease) -> Self:
        return cls(
            oid=release.oid,
            ordinal=release.ordinal,
            version=CourseReleaseVersionSchema(
                major=release.version.major,
                minor=release.version.minor,
                patch=release.version.patch,
            ),
            kind=release.kind,
            notes=release.notes.value if release.notes is not None else None,
            released_at=release.released_at,
            released_by=release.released_by,
        )


class ReleaseLessonSchema(CourseDraftLessonSchema):
    """Lesson projection inside a release tree.

    Subclasses :class:`CourseDraftLessonSchema` to inherit shape +
    discriminated-union ``blocks`` field. The OpenAPI schema name
    is ``ReleaseLessonSchema`` and is rendered separately so SDK
    consumers can keep release vs. draft types distinct.
    """

    @classmethod
    def from_release_view(cls, view: ReleaseLessonView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            position=view.position,
            blocks=[_block_view_to_schema(b) for b in view.blocks],
        )


class ReleaseModuleSchema(CourseDraftModuleSchema):
    """Module projection inside a release tree."""

    lessons: list[ReleaseLessonSchema]  # type: ignore[assignment]

    @classmethod
    def from_release_view(cls, view: ReleaseModuleView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            description=view.description,
            position=view.position,
            lessons=[ReleaseLessonSchema.from_release_view(ls) for ls in view.lessons],
        )


class CourseReleaseContentSchema(BaseModel):
    """Full content tree of a specific release."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d",
                    "course_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "ordinal": 3,
                    "version": {"major": 1, "minor": 1, "patch": 0},
                    "kind": "minor",
                    "notes": None,
                    "released_at": "2026-05-01T10:00:00+00:00",
                    "modules": [],
                },
            ],
        },
    )

    release_id: UUID
    course_id: UUID
    ordinal: int
    version: CourseReleaseVersionSchema
    kind: CourseReleaseKind
    notes: str | None
    released_at: datetime
    modules: list[ReleaseModuleSchema]

    @classmethod
    def from_view(cls, view: CourseReleaseContentView) -> Self:
        return cls(
            release_id=view.release_id,
            course_id=view.product_id,
            ordinal=view.ordinal,
            version=CourseReleaseVersionSchema(
                major=view.major,
                minor=view.minor,
                patch=view.patch,
            ),
            kind=view.kind,
            notes=view.notes,
            released_at=view.released_at,
            modules=[ReleaseModuleSchema.from_release_view(m) for m in view.modules],
        )


# ============================== routes ============================== #


@router.post(
    "/{course_id}/releases",
    summary="Create a new release of a course (snapshots draft content)",
    operation_id="createCourseRelease",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CourseReleaseSummarySchema,
    error_map=_COURSE_AUTHOR_MAP,
)
async def create_release(
    request: Request,
    payload: CreateCourseReleaseSchema,
    interactor: FromDishka[CreateCourseReleaseCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> CourseReleaseSummarySchema:
    """Snapshot the current draft as a new immutable release.

    The release row is created first, then the draft modules /
    lessons / blocks are copied into the snapshot mirror tables
    in a single transaction. If this is the first release of the
    course, the product's status flips to ``PUBLISHED`` —
    courses are not published any other way.

    Args:
        request: Source of the access cookie.
        payload: ``{"kind": "major"|"minor"|"patch", "notes": str|null}``.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID.

    Returns:
        ``201 Created`` with :class:`CourseReleaseSummarySchema`.
        Clients can fetch contents via
        ``GET /products/{id}/releases/{release_id}/content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — course not found.
        NotACourseError: HTTP 409 — product is a webinar.
        FieldError: HTTP 422 — release-notes VO violation.
    """
    ctx = await auth.authenticate(request)
    release = await interactor.run(
        CreateCourseReleaseCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
            kind=payload.kind,
            notes=payload.notes,
        ),
    )
    return CourseReleaseSummarySchema.from_entity(release)


@router.get(
    "/{course_id}/releases",
    summary="List releases of a course (newest first)",
    operation_id="listCourseReleases",
    dependencies=_AUTH_SECURITY,
    response_model=list[CourseReleaseSummarySchema],
    error_map=_COURSE_AUTHOR_MAP,
)
async def list_releases(
    request: Request,
    interactor: FromDishka[ListCourseReleasesQueryHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> list[CourseReleaseSummarySchema]:
    """Return all releases of a course, newest first. Author-only.

    Returns:
        List of :class:`CourseReleaseSummarySchema` ordered by
        ``ordinal`` descending.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        NotACourseError: HTTP 409.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListCourseReleasesQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
        ),
    )
    return [CourseReleaseSummarySchema.from_view(v) for v in views]


@router.get(
    "/{course_id}/releases/{release_id}/content",
    summary="Read the content tree of a specific release",
    operation_id="getCourseReleaseContent",
    dependencies=_AUTH_SECURITY,
    response_model=CourseReleaseContentSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def get_release_content(
    request: Request,
    interactor: FromDishka[GetCourseReleaseContentQueryHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    release_id: Annotated[UUID, _RELEASE_ID_PATH],
) -> CourseReleaseContentSchema:
    """Return the full content tree of one release. Author-only.

    Returns:
        :class:`CourseReleaseContentSchema` — modules + lessons +
        blocks (discriminated union over ``type``), shape
        identical to the draft tree.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — product or release not
            found, or ``release_id`` doesn't belong to
            ``product_id``.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetCourseReleaseContentQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
            release_id=CourseReleaseID(release_id),
        ),
    )
    return CourseReleaseContentSchema.from_view(view)


# ============================== student route ============================== #


@student_router.get(
    "/{course_id}/content",
    summary="Read the course content I'm enrolled in",
    operation_id="getMyCourseContent",
    dependencies=_AUTH_SECURITY,
    response_model=CourseReleaseContentSchema,
    error_map=AUTHENTICATED_MAP | {EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_my_content(
    request: Request,
    interactor: FromDishka[GetMyCourseContentQueryHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> CourseReleaseContentSchema:
    """Return the pinned-release content for the calling student.

    Resolves the student's enrollment for ``product_id`` and
    serves the snapshot tree of their pinned release. Strict
    pinning — students see whatever release they enrolled into,
    even if newer releases exist. Refunded enrollments are
    treated as no access (HTTP 404).

    Args:
        request: Source of the access cookie.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID.

    Returns:
        :class:`CourseReleaseContentSchema` — the modules + lessons
        + blocks tree of the student's pinned release. Same shape
        as the author-facing release content.

    Raises:
        InvalidTokenError: HTTP 401.
        EntityNotFoundError: HTTP 404 — product missing, product
            not a course, no active enrollment for the caller, or
            the pinned release is gone.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetMyCourseContentQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
        ),
    )
    return CourseReleaseContentSchema.from_view(view)
