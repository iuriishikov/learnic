from datetime import datetime
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Discriminator, Field

from learnic.application.commands.note_block.check_answer import (
    CheckBlockAnswerCommand,
    CheckBlockAnswerCommandHandler,
    MultiChoiceAnswerPayload,
    SingleChoiceAnswerPayload,
    TextAnswerPayload,
)
from learnic.application.commands.note_block.reveal_answer import (
    RevealBlockAnswerCommand,
    RevealBlockAnswerCommandHandler,
    RevealedMultiChoice,
    RevealedSingleChoice,
    RevealedTextAnswers,
)
from learnic.application.commands.note_release.create import (
    CreateNoteReleaseCommand,
    CreateNoteReleaseCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.note_content import (
    CodeBlockView,
    FileBlockView,
    HtmlBlockView,
    KatexBlockView,
    LessonBlockView,
    MultiChoiceBlockView,
    PhotoCollageBlockView,
    RutubeVideoBlockView,
    SingleChoiceBlockView,
    TextInputBlockView,
    VideoFileBlockView,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseContentView,
    NoteReleaseSummaryView,
    ReleaseLessonView,
    ReleaseModuleView,
)
from learnic.application.queries.note_content.get import (
    GetNoteContentQuery,
    GetNoteContentQueryHandler,
)
from learnic.application.queries.note_release.get_content import (
    GetNoteReleaseContentQuery,
    GetNoteReleaseContentQueryHandler,
)
from learnic.application.queries.note_release.list_for_product import (
    ListNoteReleasesQuery,
    ListNoteReleasesQueryHandler,
)
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.entities.product.ids import ProductID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    AUTHENTICATED_OWNER_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
    PRODUCT_DOES_NOT_SUPPORT_RULE,
    WRONG_BLOCK_TYPE_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.routes.note_content import (
    ChoiceOptionSchema,
    CodeBlockSchema,
    NoteDraftLessonSchema,
    NoteDraftModuleSchema,
    FileBlockSchema,
    HtmlBlockSchema,
    KatexBlockSchema,
    PhotoCollageBlockSchema,
    RutubeVideoBlockSchema,
    VideoFileBlockSchema,
    _block_view_to_schema,
)

router = ErrorAwareRouter(
    prefix="/notes",
    tags=["NoteReleases"],
    route_class=DishkaErrorAwareRoute,
)

# Student-facing read endpoint lives under the NoteContent tag
# (it returns release content but from the *student's* enrollment
# perspective, parallel to the author-side draft tree).
student_router = ErrorAwareRouter(
    prefix="/notes",
    tags=["NoteContent"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_NOTE_ID_PATH: Final = Path(
    description="Target note product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_RELEASE_ID_PATH: Final = Path(
    description="Target release UUID.",
    examples=["7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"],
)

_NOTE_AUTHOR_MAP = AUTHENTICATED_OWNER_FIELD_MAP | {
    ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE,
}


# ============================== schemas ============================== #


class CreateNoteReleaseSchema(BaseModel):
    """Body for ``POST /notes/{note_id}/releases``."""

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

    kind: NoteReleaseKind = Field(
        description=(
            "Semver bump kind. From ``v(M.m.p)``: `patch` → "
            "`v(M.m.p+1)`, `minor` → `v(M.m+1.0)`, `major` → "
            "`v(M+1.0.0)`. First release starts from baseline "
            "``v0.0.0`` so `patch` → `v0.0.1`, etc."
        ),
        examples=[NoteReleaseKind.MINOR],
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


class NoteReleaseVersionSchema(BaseModel):
    """Semver triplet for a release."""

    major: int = Field(examples=[1])
    minor: int = Field(examples=[0])
    patch: int = Field(examples=[0])


class NoteReleaseSummarySchema(BaseModel):
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
    version: NoteReleaseVersionSchema
    kind: NoteReleaseKind
    notes: str | None
    released_at: datetime
    released_by: UUID

    @classmethod
    def from_view(cls, view: NoteReleaseSummaryView) -> Self:
        return cls(
            oid=view.oid,
            ordinal=view.ordinal,
            version=NoteReleaseVersionSchema(
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
    def from_entity(cls, release: NoteRelease) -> Self:
        return cls(
            oid=release.oid,
            ordinal=release.ordinal,
            version=NoteReleaseVersionSchema(
                major=release.version.major,
                minor=release.version.minor,
                patch=release.version.patch,
            ),
            kind=release.kind,
            notes=release.notes.value if release.notes is not None else None,
            released_at=release.released_at,
            released_by=release.released_by,
        )


class ReleaseLessonSchema(NoteDraftLessonSchema):
    """Lesson projection inside a release tree.

    Subclasses :class:`NoteDraftLessonSchema` to inherit shape +
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


class ReleaseModuleSchema(NoteDraftModuleSchema):
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


class NoteReleaseContentSchema(BaseModel):
    """Full content tree of a specific release."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d",
                    "note_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
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
    note_id: UUID
    ordinal: int
    version: NoteReleaseVersionSchema
    kind: NoteReleaseKind
    notes: str | None
    released_at: datetime
    modules: list[ReleaseModuleSchema]

    @classmethod
    def from_view(cls, view: NoteReleaseContentView) -> Self:
        return cls(
            release_id=view.release_id,
            note_id=view.product_id,
            ordinal=view.ordinal,
            version=NoteReleaseVersionSchema(
                major=view.major,
                minor=view.minor,
                patch=view.patch,
            ),
            kind=view.kind,
            notes=view.notes,
            released_at=view.released_at,
            modules=[ReleaseModuleSchema.from_release_view(m) for m in view.modules],
        )


# ============================== public block schemas ============================== #
#
# Student-facing projections of the three interactive answer blocks.
# Strip ``correct_option_id`` / ``correct_option_ids`` / ``accepted_answers``
# — those live server-side only. Passive blocks (html / katex / video /
# code) carry no answer to hide and reuse their authoring schemas
# verbatim.


class PublicSingleChoiceBlockSchema(BaseModel):
    """Single-choice block as exposed to a learner.

    Carries the question options but NOT the correct id. The
    learner submits a choice via the check endpoint; the server
    answers ``is_correct`` without leaking the right answer.
    """

    type: Literal[BlockType.SINGLE_CHOICE] = Field(
        default=BlockType.SINGLE_CHOICE,
        description="Discriminator — always `single_choice`.",
    )
    oid: UUID
    position: int
    options: list[ChoiceOptionSchema]

    @classmethod
    def from_view(cls, view: SingleChoiceBlockView) -> Self:
        return cls(
            type=BlockType.SINGLE_CHOICE,
            oid=view.oid,
            position=view.position,
            options=[ChoiceOptionSchema.from_view(o) for o in view.options],
        )


class PublicMultiChoiceBlockSchema(BaseModel):
    """Multi-choice block as exposed to a learner (no correct set)."""

    type: Literal[BlockType.MULTI_CHOICE] = Field(
        default=BlockType.MULTI_CHOICE,
        description="Discriminator — always `multi_choice`.",
    )
    oid: UUID
    position: int
    options: list[ChoiceOptionSchema]

    @classmethod
    def from_view(cls, view: MultiChoiceBlockView) -> Self:
        return cls(
            type=BlockType.MULTI_CHOICE,
            oid=view.oid,
            position=view.position,
            options=[ChoiceOptionSchema.from_view(o) for o in view.options],
        )


class PublicTextInputBlockSchema(BaseModel):
    """Text-input block as exposed to a learner.

    Accepts the normalisation flags so the SPA can hint at casing
    or whitespace expectations; the accepted-answer list itself is
    server-side only.
    """

    type: Literal[BlockType.TEXT_INPUT] = Field(
        default=BlockType.TEXT_INPUT,
        description="Discriminator — always `text_input`.",
    )
    oid: UUID
    position: int
    case_sensitive: bool
    trim_whitespace: bool

    @classmethod
    def from_view(cls, view: TextInputBlockView) -> Self:
        return cls(
            type=BlockType.TEXT_INPUT,
            oid=view.oid,
            position=view.position,
            case_sensitive=view.case_sensitive,
            trim_whitespace=view.trim_whitespace,
        )


_PublicLessonBlockSchemaUnion = (
    HtmlBlockSchema
    | KatexBlockSchema
    | RutubeVideoBlockSchema
    | CodeBlockSchema
    | PublicSingleChoiceBlockSchema
    | PublicMultiChoiceBlockSchema
    | PublicTextInputBlockSchema
    | FileBlockSchema
    | VideoFileBlockSchema
    | PhotoCollageBlockSchema
)

PublicLessonBlockSchema = Annotated[
    _PublicLessonBlockSchemaUnion,
    Discriminator("type"),
]


def _block_view_to_public_schema(
    view: LessonBlockView,
) -> _PublicLessonBlockSchemaUnion:
    """Same dispatch as :func:`_block_view_to_schema` but strips secrets.

    Passive blocks (html / katex / code / video) carry no answer
    to hide and reuse their authoring schemas verbatim — only the
    three interactive types get distinct public schemas.
    """
    if isinstance(view, HtmlBlockView):
        return HtmlBlockSchema.from_view(view)
    if isinstance(view, KatexBlockView):
        return KatexBlockSchema.from_view(view)
    if isinstance(view, CodeBlockView):
        return CodeBlockSchema.from_view(view)
    if isinstance(view, SingleChoiceBlockView):
        return PublicSingleChoiceBlockSchema.from_view(view)
    if isinstance(view, MultiChoiceBlockView):
        return PublicMultiChoiceBlockSchema.from_view(view)
    if isinstance(view, TextInputBlockView):
        return PublicTextInputBlockSchema.from_view(view)
    if isinstance(view, RutubeVideoBlockView):
        return RutubeVideoBlockSchema.from_view(view)
    if isinstance(view, FileBlockView):
        return FileBlockSchema.from_view(view)
    if isinstance(view, VideoFileBlockView):
        return VideoFileBlockSchema.from_view(view)
    if isinstance(view, PhotoCollageBlockView):
        return PhotoCollageBlockSchema.from_view(view)
    # mypy exhaustiveness — all variants of LessonBlockView are listed.
    msg = f"unknown lesson block view: {type(view).__name__!r}"
    raise RuntimeError(msg)


class PublicReleaseLessonSchema(BaseModel):
    """Lesson projection for the student-facing content tree."""

    oid: UUID
    title: str
    position: int
    blocks: list[PublicLessonBlockSchema]

    @classmethod
    def from_release_view(cls, view: ReleaseLessonView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            position=view.position,
            blocks=[_block_view_to_public_schema(b) for b in view.blocks],
        )


class PublicReleaseModuleSchema(BaseModel):
    """Module projection for the student-facing content tree."""

    oid: UUID
    title: str
    description: str | None
    position: int
    lessons: list[PublicReleaseLessonSchema]

    @classmethod
    def from_release_view(cls, view: ReleaseModuleView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            description=view.description,
            position=view.position,
            lessons=[
                PublicReleaseLessonSchema.from_release_view(ls) for ls in view.lessons
            ],
        )


class PublicNoteReleaseContentSchema(BaseModel):
    """Student-facing release content tree.

    Same shape as :class:`NoteReleaseContentSchema` but the
    interactive blocks inside don't carry their correct answers.
    Use this for any endpoint a learner can hit; reserve the
    authoring schema for endpoints behind ``READ_PRODUCT`` (i.e.
    collaborators only).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d",
                    "note_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
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
    note_id: UUID
    ordinal: int
    version: NoteReleaseVersionSchema
    kind: NoteReleaseKind
    notes: str | None
    released_at: datetime
    modules: list[PublicReleaseModuleSchema]

    @classmethod
    def from_view(cls, view: NoteReleaseContentView) -> Self:
        return cls(
            release_id=view.release_id,
            note_id=view.product_id,
            ordinal=view.ordinal,
            version=NoteReleaseVersionSchema(
                major=view.major,
                minor=view.minor,
                patch=view.patch,
            ),
            kind=view.kind,
            notes=view.notes,
            released_at=view.released_at,
            modules=[
                PublicReleaseModuleSchema.from_release_view(m) for m in view.modules
            ],
        )


# ============================== check / reveal schemas ============================== #


_BLOCK_ID_PATH: Final = Path(
    description="Release-side block UUID (from the student content tree).",
    examples=["d1e2f3a4-5b6c-4d7e-8f90-1a2b3c4d5e6f"],
)


class CheckSingleChoicePayload(BaseModel):
    type: Literal[BlockType.SINGLE_CHOICE] = Field(
        default=BlockType.SINGLE_CHOICE,
    )
    option_id: UUID = Field(
        description="The id of the option the student picked.",
    )


class CheckMultiChoicePayload(BaseModel):
    type: Literal[BlockType.MULTI_CHOICE] = Field(
        default=BlockType.MULTI_CHOICE,
    )
    option_ids: list[UUID] = Field(
        description=(
            "The ids of options the student picked. Order does not "
            "matter — server compares as a set."
        ),
        min_length=0,
    )


class CheckTextInputPayload(BaseModel):
    type: Literal[BlockType.TEXT_INPUT] = Field(
        default=BlockType.TEXT_INPUT,
    )
    answer: str = Field(
        description="The text the student typed in. Sent verbatim.",
        min_length=0,
        max_length=2_000,
    )


CheckBlockAnswerSchema = Annotated[
    CheckSingleChoicePayload | CheckMultiChoicePayload | CheckTextInputPayload,
    Discriminator("type"),
]


class BlockCheckResultSchema(BaseModel):
    """Response of ``POST .../check``. Only ``is_correct`` is exposed."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"is_correct": True}]},
    )

    is_correct: bool = Field(
        description=(
            "True iff the submission matches the block's correct "
            "answer under the block's own comparison rules."
        ),
    )


class RevealedSingleChoiceSchema(BaseModel):
    type: Literal[BlockType.SINGLE_CHOICE] = Field(
        default=BlockType.SINGLE_CHOICE,
    )
    option_id: UUID


class RevealedMultiChoiceSchema(BaseModel):
    type: Literal[BlockType.MULTI_CHOICE] = Field(
        default=BlockType.MULTI_CHOICE,
    )
    option_ids: list[UUID]


class RevealedTextAnswersSchema(BaseModel):
    type: Literal[BlockType.TEXT_INPUT] = Field(
        default=BlockType.TEXT_INPUT,
    )
    answers: list[str] = Field(
        description=(
            "All accepted spellings. The SPA can show them as a "
            "spectrum (e.g. \"Paris\" / \"paris\")."
        ),
    )


RevealedAnswerSchema = Annotated[
    RevealedSingleChoiceSchema | RevealedMultiChoiceSchema | RevealedTextAnswersSchema,
    Discriminator("type"),
]


# ============================== routes ============================== #


@router.post(
    "/{note_id}/releases",
    summary="Create a new release of a note (snapshots draft content)",
    operation_id="createNoteRelease",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=NoteReleaseSummarySchema,
    error_map=_NOTE_AUTHOR_MAP,
)
async def create_release(
    request: Request,
    payload: CreateNoteReleaseSchema,
    interactor: FromDishka[CreateNoteReleaseCommandHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
) -> NoteReleaseSummarySchema:
    """Snapshot the current draft as a new immutable release.

    The release row is created first, then the draft modules /
    lessons / blocks are copied into the snapshot mirror tables
    in a single transaction. If this is the first release of the
    note, the product's status flips to ``PUBLISHED`` —
    notes are not published any other way.

    Args:
        request: Source of the access cookie.
        payload: ``{"kind": "major"|"minor"|"patch", "notes": str|null}``.
        interactor: Injected handler.
        auth: Injected authenticator.
        note_id: Note product UUID.

    Returns:
        ``201 Created`` with :class:`NoteReleaseSummarySchema`.
        Clients can fetch contents via
        ``GET /products/{id}/releases/{release_id}/content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — note not found.
        ProductDoesNotSupportError: HTTP 409 — product is not a
            note (no release-related capabilities).
        ResourceLimitReachedError: HTTP 409 — the note already has
            ``NOTE_RELEASE_LIMIT`` releases.
        FieldError: HTTP 422 — release-notes VO violation.
    """
    ctx = await auth.authenticate(request)
    release = await interactor.run(
        CreateNoteReleaseCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(note_id),
            kind=payload.kind,
            notes=payload.notes,
        ),
    )
    return NoteReleaseSummarySchema.from_entity(release)


@router.get(
    "/{note_id}/releases",
    summary="List releases of a note (newest first)",
    operation_id="listNoteReleases",
    dependencies=_AUTH_SECURITY,
    response_model=list[NoteReleaseSummarySchema],
    error_map=_NOTE_AUTHOR_MAP,
)
async def list_releases(
    request: Request,
    interactor: FromDishka[ListNoteReleasesQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
) -> list[NoteReleaseSummarySchema]:
    """Return all releases of a note, newest first.

    Caller needs ``READ_PRODUCT`` on the product (owner or any
    collaborator with that permission).

    Returns:
        List of :class:`NoteReleaseSummarySchema` ordered by
        ``ordinal`` descending.

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller has no
            collaboration with ``READ_PRODUCT``.
        EntityNotFoundError: HTTP 404.
        ProductDoesNotSupportError: HTTP 409 — product is not a note.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListNoteReleasesQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(note_id),
        ),
    )
    return [NoteReleaseSummarySchema.from_view(v) for v in views]


@router.get(
    "/{note_id}/releases/{release_id}/content",
    summary="Read the content tree of a specific release",
    operation_id="getNoteReleaseContent",
    dependencies=_AUTH_SECURITY,
    response_model=NoteReleaseContentSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def get_release_content(
    request: Request,
    interactor: FromDishka[GetNoteReleaseContentQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
    release_id: Annotated[UUID, _RELEASE_ID_PATH],
) -> NoteReleaseContentSchema:
    """Return the full content tree of one release.

    Caller needs ``READ_PRODUCT`` on the product (owner or any
    collaborator with that permission).

    Returns:
        :class:`NoteReleaseContentSchema` — modules + lessons +
        blocks (discriminated union over ``type``), shape
        identical to the draft tree.

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller has no
            collaboration with ``READ_PRODUCT``.
        EntityNotFoundError: HTTP 404 — product or release not
            found, or ``release_id`` doesn't belong to
            ``product_id``.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetNoteReleaseContentQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(note_id),
            release_id=NoteReleaseID(release_id),
        ),
    )
    return NoteReleaseContentSchema.from_view(view)


# ============================== student route ============================== #


@student_router.get(
    "/{note_id}/content",
    summary="Read note content (own enrollment or latest published)",
    operation_id="getNoteContent",
    response_model=PublicNoteReleaseContentSchema,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_content(
    request: Request,
    interactor: FromDishka[GetNoteContentQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
) -> PublicNoteReleaseContentSchema:
    """Return note content for the current viewer.

    Public endpoint — the access cookie is read opportunistically
    via :meth:`Authenticator.authenticate_optional`. The resolution
    matrix is:

    * Caller has an ``ACTIVE`` enrollment for this note → their
      **pinned** release. Strict pinning still holds; students do
      not auto-upgrade.
    * Anyone else (anonymous, signed-in but not enrolled, refunded /
      revoked enrollments) viewing a ``PUBLISHED`` note → the
      **latest** release of the product.
    * Anything else (product missing, not a note, or in a
      non-``PUBLISHED`` state with no active enrollment) → 404.

    Blocks are projected through the **public** schema set:
    correct answers for interactive blocks are stripped
    server-side. Check / reveal endpoints still require an active
    enrollment.

    Args:
        request: Source of the access cookie (optional).
        interactor: Injected handler.
        auth: Injected authenticator (used opportunistically).
        note_id: Note product UUID.

    Returns:
        :class:`PublicNoteReleaseContentSchema` — student-safe
        projection of the chosen release tree.

    Raises:
        EntityNotFoundError: HTTP 404 — product missing, product
            not a note, or no release is available to this
            viewer under the rules above.
    """
    ctx = await auth.authenticate_optional(request)
    view = await interactor.run(
        GetNoteContentQuery(
            actor_id=ctx.user_id if ctx is not None else None,
            product_id=ProductID(note_id),
        ),
    )
    return PublicNoteReleaseContentSchema.from_view(view)


# ============================== check / reveal routes ============================== #


def _to_command_payload(
    payload: CheckSingleChoicePayload
    | CheckMultiChoicePayload
    | CheckTextInputPayload,
) -> SingleChoiceAnswerPayload | MultiChoiceAnswerPayload | TextAnswerPayload:
    if isinstance(payload, CheckSingleChoicePayload):
        return SingleChoiceAnswerPayload(
            option_id=ChoiceOptionID(payload.option_id),
        )
    if isinstance(payload, CheckMultiChoicePayload):
        return MultiChoiceAnswerPayload(
            option_ids=frozenset(
                ChoiceOptionID(o) for o in payload.option_ids
            ),
        )
    return TextAnswerPayload(answer=payload.answer)


@student_router.post(
    "/{note_id}/release-blocks/{block_id}/check",
    summary="Submit an answer for an interactive block and learn correctness",
    operation_id="checkBlockAnswer",
    dependencies=_AUTH_SECURITY,
    response_model=BlockCheckResultSchema,
    error_map=AUTHENTICATED_MAP
    | {
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
    },
)
async def check_block_answer(
    request: Request,
    payload: CheckBlockAnswerSchema,
    interactor: FromDishka[CheckBlockAnswerCommandHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> BlockCheckResultSchema:
    """Check the learner's submission against the server-side answer.

    Wrong submissions return ``is_correct=false`` and nothing more —
    the correct answer is not leaked. To see it, call the reveal
    endpoint. Submitting a payload of the wrong shape for the block
    yields 409.

    Args:
        request: Source of the access cookie.
        payload: Discriminated union (single / multi / text) —
            shape must match the block's type.
        interactor: Injected handler.
        auth: Injected authenticator.
        note_id: Note product UUID.
        block_id: Release-side block UUID.

    Returns:
        :class:`BlockCheckResultSchema` — ``{is_correct: bool}``.

    Raises:
        InvalidTokenError: HTTP 401.
        EntityNotFoundError: HTTP 404 — block / product missing or
            caller is not actively enrolled.
        WrongBlockTypeError: HTTP 409 — payload shape doesn't fit
            the block's type, or the block is not an answer block.
    """
    del note_id
    ctx = await auth.authenticate(request)
    result = await interactor.run(
        CheckBlockAnswerCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            payload=_to_command_payload(payload),
        ),
    )
    return BlockCheckResultSchema(is_correct=result.is_correct)


def _to_reveal_schema(
    answer: RevealedSingleChoice | RevealedMultiChoice | RevealedTextAnswers,
) -> RevealedSingleChoiceSchema | RevealedMultiChoiceSchema | RevealedTextAnswersSchema:
    if isinstance(answer, RevealedSingleChoice):
        return RevealedSingleChoiceSchema(option_id=UUID(str(answer.option_id)))
    if isinstance(answer, RevealedMultiChoice):
        return RevealedMultiChoiceSchema(
            option_ids=[UUID(str(o)) for o in answer.option_ids],
        )
    return RevealedTextAnswersSchema(answers=list(answer.answers))


@student_router.post(
    "/{note_id}/release-blocks/{block_id}/reveal",
    summary="Reveal the correct answer for an interactive block",
    operation_id="revealBlockAnswer",
    dependencies=_AUTH_SECURITY,
    response_model=RevealedAnswerSchema,
    error_map=AUTHENTICATED_MAP
    | {
        EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
    },
)
async def reveal_block_answer(
    request: Request,
    interactor: FromDishka[RevealBlockAnswerCommandHandler],
    auth: FromDishka[Authenticator],
    note_id: Annotated[UUID, _NOTE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> (
    RevealedSingleChoiceSchema
    | RevealedMultiChoiceSchema
    | RevealedTextAnswersSchema
):
    """Reveal the correct answer to a learner who has given up.

    Reveal is intentionally a separate explicit action — returning
    the correct answer alongside a wrong check response would be a
    one-shot backdoor. Calling reveal is recorded (in future
    versions) as an explicit give-up signal.

    Args:
        request: Source of the access cookie.
        interactor: Injected handler.
        auth: Injected authenticator.
        note_id: Note product UUID.
        block_id: Release-side block UUID.

    Returns:
        Discriminated reveal payload matching the block type.

    Raises:
        InvalidTokenError: HTTP 401.
        EntityNotFoundError: HTTP 404 — block / product missing or
            caller is not actively enrolled.
        WrongBlockTypeError: HTTP 409 — block isn't an answer block.
    """
    del note_id
    ctx = await auth.authenticate(request)
    answer = await interactor.run(
        RevealBlockAnswerCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
        ),
    )
    return _to_reveal_schema(answer)
