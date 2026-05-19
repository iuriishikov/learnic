from datetime import datetime, timezone
from typing import Annotated, Any, Final, Literal, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, File, Form, Path, Request, UploadFile, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Discriminator, Field

from learnic.application.commands.course_block._inputs import (
    ChoiceOptionDraftInput,
)
from learnic.application.commands.course_block.add_code import (
    AddCodeBlockCommand,
    AddCodeBlockCommandHandler,
    CodeTabInput,
)
from learnic.application.commands.course_block.add_file import (
    AddFileBlockCommand,
    AddFileBlockCommandHandler,
)
from learnic.application.commands.course_block.add_photo_collage import (
    AddPhotoCollageBlockCommand,
    AddPhotoCollageBlockCommandHandler,
    CollageItemUpload,
)
from learnic.application.commands.course_block.add_video_file import (
    AddVideoFileBlockCommand,
    AddVideoFileBlockCommandHandler,
)
from learnic.application.commands.course_block.add_html import (
    AddHtmlBlockCommand,
    AddHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.add_katex import (
    AddKatexBlockCommand,
    AddKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.add_multi_choice import (
    AddMultiChoiceBlockCommand,
    AddMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_rutube_video import (
    AddRutubeVideoBlockCommand,
    AddRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.add_single_choice import (
    AddSingleChoiceBlockCommand,
    AddSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_text_input import (
    AddTextInputBlockCommand,
    AddTextInputBlockCommandHandler,
)
from learnic.application.commands.course_block.delete import (
    DeleteLessonBlockCommand,
    DeleteLessonBlockCommandHandler,
)
from learnic.application.commands.course_block.reorder import (
    ReorderLessonBlocksCommand,
    ReorderLessonBlocksCommandHandler,
)
from learnic.application.commands.course_block.update_code import (
    UpdateCodeBlockCommand,
    UpdateCodeBlockCommandHandler,
)
from learnic.application.commands.course_block.update_file import (
    UpdateFileBlockCommand,
    UpdateFileBlockCommandHandler,
)
from learnic.application.commands.course_block.update_photo_collage import (
    UpdatePhotoCollageBlockCommand,
    UpdatePhotoCollageBlockCommandHandler,
)
from learnic.application.commands.course_block.update_video_file import (
    UpdateVideoFileBlockCommand,
    UpdateVideoFileBlockCommandHandler,
)
from learnic.application.commands.course_block.update_html import (
    UpdateHtmlBlockCommand,
    UpdateHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.update_katex import (
    UpdateKatexBlockCommand,
    UpdateKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.update_multi_choice import (
    UpdateMultiChoiceBlockCommand,
    UpdateMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_rutube_video import (
    UpdateRutubeVideoBlockCommand,
    UpdateRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.update_single_choice import (
    UpdateSingleChoiceBlockCommand,
    UpdateSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_text_input import (
    UpdateTextInputBlockCommand,
    UpdateTextInputBlockCommandHandler,
)
from learnic.application.commands.course_draft.reset import (
    ResetCourseDraftCommand,
    ResetCourseDraftCommandHandler,
)
from learnic.application.commands.course_lesson.add import (
    AddCourseLessonCommand,
    AddCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.delete import (
    DeleteCourseLessonCommand,
    DeleteCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.move import (
    MoveCourseLessonCommand,
    MoveCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.rename import (
    RenameCourseLessonCommand,
    RenameCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.reorder import (
    ReorderCourseLessonsCommand,
    ReorderCourseLessonsCommandHandler,
)
from learnic.application.commands.course_module.add import (
    AddCourseModuleCommand,
    AddCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.delete import (
    DeleteCourseModuleCommand,
    DeleteCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.rename import (
    RenameCourseModuleCommand,
    RenameCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.reorder import (
    ReorderCourseModulesCommand,
    ReorderCourseModulesCommandHandler,
)
from learnic.application.commands.course_module.update_description import (
    UpdateCourseModuleDescriptionCommand,
    UpdateCourseModuleDescriptionCommandHandler,
)
from learnic.application.common.errors import (
    CrossCourseLessonMoveError,
    InvalidReorderError,
    StorageQuotaExceededError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.course_content import (
    ChoiceOptionView,
    CodeBlockView,
    CollageItemView,
    CourseDraftView,
    DraftLessonView,
    DraftModuleView,
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
from learnic.application.queries.course_content.get_draft import (
    GetCourseDraftQuery,
    GetCourseDraftQueryHandler,
)
from learnic.entities.course_block.constants import (
    BLOCK_TITLE_MAX_LEN,
    CHOICE_BLOCK_MAX_OPTIONS,
    CHOICE_BLOCK_MIN_OPTIONS,
    CHOICE_OPTION_LABEL_MAX_LEN,
    CODE_BLOCK_MAX_LEN,
    CODE_BLOCK_MAX_TABS,
    CODE_TAB_LABEL_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    PHOTO_COLLAGE_CAPTION_MAX_LEN,
    PHOTO_COLLAGE_MAX_ITEMS,
    PHOTO_COLLAGE_MIN_ITEMS,
    TEXT_INPUT_ANSWER_MAX_LEN,
    TEXT_INPUT_MAX_ACCEPTED,
    TEXT_INPUT_MIN_ACCEPTED,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.enums import BlockType, CodeBlockLanguage
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.entities.product.ids import ProductID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.upload_limits import (
    LESSON_COLLAGE_ITEM_MAX_BYTES,
    LESSON_FILE_BLOCK_MAX_BYTES,
    LESSON_VIDEO_BLOCK_MAX_BYTES,
)
from learnic.presentation.http.common.uploads import read_upload
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    CROSS_COURSE_LESSON_MOVE_RULE,
    INVALID_REORDER_RULE,
    PRODUCT_DOES_NOT_SUPPORT_RULE,
    STORAGE_QUOTA_EXCEEDED_RULE,
    WRONG_BLOCK_TYPE_RULE,
    WRONG_FILE_CONTENT_TYPE_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import FileSchema

router = ErrorAwareRouter(
    prefix="/courses",
    tags=["CourseContent"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COURSE_ID_PATH: Final = Path(
    description="Target course product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_MODULE_ID_PATH: Final = Path(
    description="Target module's UUID.",
    examples=["a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d"],
)
_LESSON_ID_PATH: Final = Path(
    description="Target lesson's UUID.",
    examples=["b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"],
)


# ============================== schemas ============================== #


class AddCourseModuleSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/modules``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"title": "Введение", "description": "Обзор курса."},
            ],
        },
    )

    title: str = Field(
        description=(
            "Module title. Required, non-empty. "
            f"Max length {MODULE_TITLE_MAX_LEN} chars "
            "(`MODULE_TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=MODULE_TITLE_MAX_LEN,
        examples=["Введение"],
    )
    description: str | None = Field(
        default=None,
        description=(
            "Optional module description. "
            f"Max length {MODULE_DESCRIPTION_MAX_LEN} chars "
            "(`MODULE_DESCRIPTION_MAX_LEN`); omit or `null` to "
            "leave empty."
        ),
        min_length=1,
        max_length=MODULE_DESCRIPTION_MAX_LEN,
        examples=["Обзор курса.", None],
    )


class RenameCourseModuleSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/modules/{module_id}/title``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"title": "Async Python intro"}]},
    )

    title: str = Field(
        description=(f"New module title. Max length {MODULE_TITLE_MAX_LEN} chars."),
        min_length=1,
        max_length=MODULE_TITLE_MAX_LEN,
        examples=["Async Python intro"],
    )


class UpdateCourseModuleDescriptionSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/modules/{module_id}/description``.

    Send ``null`` to clear the description.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"description": "Расширенное описание модуля."}],
        },
    )

    description: str | None = Field(
        description=(
            "New module description, or `null` to clear. "
            f"Max length {MODULE_DESCRIPTION_MAX_LEN} chars."
        ),
        min_length=1,
        max_length=MODULE_DESCRIPTION_MAX_LEN,
        examples=["Расширенное описание модуля.", None],
    )


class ReorderCourseModulesSchema(BaseModel):
    """Body for ``PUT /courses/{course_id}/modules/order``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ordered_ids": [
                        "a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d",
                        "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e",
                    ],
                },
            ],
        },
    )

    ordered_ids: list[UUID] = Field(
        description=(
            "Full list of module ids in the desired order. Must "
            "match the existing module set of the course exactly."
        ),
        examples=[
            [
                "a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d",
                "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e",
            ],
        ],
    )


class CreatedCourseModuleSchema(BaseModel):
    """Response for ``POST /courses/{course_id}/modules``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created module.",
        examples=["a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d"],
    )


class AddCourseLessonSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/modules/{module_id}/lessons``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"title": "Урок 1: Введение"}]},
    )

    title: str = Field(
        description=(
            "Lesson title. Required, non-empty. "
            f"Max length {LESSON_TITLE_MAX_LEN} chars "
            "(`LESSON_TITLE_MAX_LEN`)."
        ),
        min_length=1,
        max_length=LESSON_TITLE_MAX_LEN,
        examples=["Урок 1: Введение"],
    )


class RenameCourseLessonSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/lessons/{lesson_id}/title``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"title": "Что такое asyncio"}]},
    )

    title: str = Field(
        description=(f"New lesson title. Max length {LESSON_TITLE_MAX_LEN} chars."),
        min_length=1,
        max_length=LESSON_TITLE_MAX_LEN,
        examples=["Что такое asyncio"],
    )


class MoveCourseLessonSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/lessons/{lesson_id}/move``.

    Moves the lesson to the end of the target module within the
    same course. Cross-course moves are rejected with HTTP 409.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"target_module_id": "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"},
            ],
        },
    )

    target_module_id: UUID = Field(
        description="UUID of the module to move the lesson into.",
        examples=["b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"],
    )


class ReorderCourseLessonsSchema(BaseModel):
    """Body for ``PUT /courses/{course_id}/modules/{module_id}/lessons/order``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ordered_ids": [
                        "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e",
                        "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                    ],
                },
            ],
        },
    )

    ordered_ids: list[UUID] = Field(
        description=(
            "Full list of lesson ids in the desired order. Must "
            "match the existing lesson set of the module exactly."
        ),
        examples=[
            [
                "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e",
                "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
            ],
        ],
    )


class CreatedCourseLessonSchema(BaseModel):
    """Response for ``POST /courses/{course_id}/modules/{module_id}/lessons``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created lesson.",
        examples=["b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"],
    )


class HtmlBlockSchema(BaseModel):
    """HTML lesson-block projection (read-only)."""

    type: Literal[BlockType.HTML] = Field(
        default=BlockType.HTML,
        description="Discriminator — always `html` for this schema.",
    )
    oid: UUID = Field(examples=["c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"])
    position: int = Field(examples=[0])
    html: str = Field(
        description="Sanitized HTML body of the block.",
        examples=["<p>Hello</p>"],
    )

    @classmethod
    def from_view(cls, view: HtmlBlockView) -> Self:
        return cls(
            type=BlockType.HTML,
            oid=view.oid,
            position=view.position,
            html=view.html,
        )


class KatexBlockSchema(BaseModel):
    """KaTeX lesson-block projection (read-only).

    Body holds KaTeX-flavored math source — a strict subset of LaTeX
    that the frontend renders via the KaTeX library. See
    https://katex.org/docs/support_table.html for the supported
    command surface; full LaTeX documents (``\\begin{document}``,
    text-mode packages, etc.) will not render.
    """

    type: Literal[BlockType.KATEX] = Field(
        default=BlockType.KATEX,
        description="Discriminator — always `katex` for this schema.",
    )
    oid: UUID = Field(examples=["d4e5f6a7-8b9c-4d0e-1f2a-4b5c6d7e8f9a"])
    position: int = Field(examples=[1])
    source: str = Field(
        description=(
            "Raw KaTeX-compatible math source. Subset of LaTeX — "
            "see https://katex.org/docs/support_table.html. "
            "Frontend renders via KaTeX."
        ),
        examples=[r"\int_0^1 x^2\, dx"],
    )

    @classmethod
    def from_view(cls, view: KatexBlockView) -> Self:
        return cls(
            type=BlockType.KATEX,
            oid=view.oid,
            position=view.position,
            source=view.source,
        )


def _rutube_embed_url(external_id: str) -> str:
    return f"https://rutube.ru/play/embed/{external_id}/"


class RutubeVideoBlockSchema(BaseModel):
    """Rutube-embed lesson-block projection (read-only).

    There is no shared "video" schema — provider-specific embeds
    have provider-specific shapes (id format, embed URL template).
    Adding a new provider means adding a new ``<Provider>VideoBlockSchema``
    and extending the discriminated union below.

    ``embed_url`` is computed server-side as
    ``https://rutube.ru/play/embed/{external_id}/`` so the
    frontend can drop it into an ``<iframe>`` without knowing
    the template.
    """

    type: Literal[BlockType.RUTUBE_VIDEO] = Field(
        default=BlockType.RUTUBE_VIDEO,
        description="Discriminator — always `rutube_video` for this schema.",
    )
    oid: UUID = Field(examples=["e5f6a7b8-9c0d-4e1f-2a3b-4c5d6e7f8a9b"])
    position: int = Field(examples=[2])
    external_id: str = Field(
        description="Rutube video id — 32-char lowercase hex.",
        examples=["f9bb1e0bdfac28c93c2c35a45f87f3eb"],
    )
    embed_url: str = Field(
        description=(
            "Pre-built Rutube URL for an `<iframe>` embed. "
            "Computed server-side from `external_id`."
        ),
        examples=[
            "https://rutube.ru/play/embed/f9bb1e0bdfac28c93c2c35a45f87f3eb/",
        ],
    )
    title: str | None = Field(
        default=None,
        description="Optional human-readable caption.",
        examples=["Lecture 1: Introduction", None],
    )

    @classmethod
    def from_view(cls, view: RutubeVideoBlockView) -> Self:
        return cls(
            type=BlockType.RUTUBE_VIDEO,
            oid=view.oid,
            position=view.position,
            external_id=view.external_id,
            embed_url=_rutube_embed_url(view.external_id),
            title=view.title,
        )


class CodeTabSchema(BaseModel):
    """One tab inside a :class:`CodeBlockSchema`.

    A code block always carries a non-empty ``tabs`` list. For
    single-tab blocks the frontend hides the tab strip; for
    multi-tab blocks (e.g. ``npm`` / ``pnpm`` / ``yarn``) every
    label must be non-empty and unique.
    """

    label: str = Field(
        description=(
            "Tab label shown in the strip. Empty string is only "
            "allowed when the block has a single tab. "
            f"Max length {CODE_TAB_LABEL_MAX_LEN} chars."
        ),
        max_length=CODE_TAB_LABEL_MAX_LEN,
        examples=["npm", "pnpm", "yarn"],
    )
    source: str = Field(
        description=(
            "Verbatim source code for this tab. Whitespace is "
            f"preserved; may be empty. Max length {CODE_BLOCK_MAX_LEN} chars."
        ),
        max_length=CODE_BLOCK_MAX_LEN,
        examples=["npm install react"],
    )
    language: CodeBlockLanguage = Field(
        description=(
            "Syntax-highlight language for this tab. Matches the "
            "frontend tokenizer's supported set."
        ),
        examples=[CodeBlockLanguage.BASH],
    )


class CodeBlockSchema(BaseModel):
    """Source-code lesson-block projection (read-only).

    A code block holds one or more tabs (variants). The most
    common case is a single tab — the tab strip is hidden client-
    side. Multi-tab blocks carry variant snippets like ``npm`` /
    ``pnpm`` / ``yarn`` that share intent but differ in tooling.
    """

    type: Literal[BlockType.CODE] = Field(
        default=BlockType.CODE,
        description="Discriminator — always `code` for this schema.",
    )
    oid: UUID = Field(examples=["f6a7b8c9-0d1e-4f2a-3b4c-5d6e7f8a9b0c"])
    position: int = Field(examples=[3])
    tabs: list[CodeTabSchema] = Field(
        description=(
            "Ordered list of code variants. Always non-empty; "
            f"capped at {CODE_BLOCK_MAX_TABS} tabs (`CODE_BLOCK_MAX_TABS`)."
        ),
        min_length=1,
        max_length=CODE_BLOCK_MAX_TABS,
    )

    @classmethod
    def from_view(cls, view: CodeBlockView) -> Self:
        return cls(
            type=BlockType.CODE,
            oid=view.oid,
            position=view.position,
            tabs=[
                CodeTabSchema(
                    label=t.label,
                    source=t.source,
                    language=CodeBlockLanguage(t.language),
                )
                for t in view.tabs
            ],
        )


class ChoiceOptionSchema(BaseModel):
    """One selectable option inside a choice block (read-only)."""

    oid: UUID = Field(
        description="Stable option id (survives reorder / label edits).",
        examples=["c1d2e3f4-5678-4abc-9012-3456789abcde"],
    )
    label: str = Field(
        description=(
            "Plain-text option caption. Empty string is valid: a "
            "freshly created block ships with placeholder options "
            "the author fills in afterwards (mirroring the VO). "
            f"Max {CHOICE_OPTION_LABEL_MAX_LEN} chars "
            "(`CHOICE_OPTION_LABEL_MAX_LEN`)."
        ),
        max_length=CHOICE_OPTION_LABEL_MAX_LEN,
        examples=["Paris", ""],
    )

    @classmethod
    def from_view(cls, view: ChoiceOptionView) -> Self:
        return cls(oid=UUID(view.oid), label=view.label)


class SingleChoiceBlockSchema(BaseModel):
    """Single-choice answer block projection (authoring-side, read-only).

    The question prompt itself is NOT part of this block — it lives
    in a preceding HTML block. This schema carries only the answer
    field configuration. ``correct_option_id`` is included because
    this projection is for authors; the student-facing public view
    drops it (see release-content endpoints).
    """

    type: Literal[BlockType.SINGLE_CHOICE] = Field(
        default=BlockType.SINGLE_CHOICE,
        description="Discriminator — always `single_choice` for this schema.",
    )
    oid: UUID = Field(examples=["d1e2f3a4-5b6c-4d7e-8f90-1a2b3c4d5e6f"])
    position: int = Field(examples=[2])
    options: list[ChoiceOptionSchema] = Field(
        description=(
            f"Between {CHOICE_BLOCK_MIN_OPTIONS} and "
            f"{CHOICE_BLOCK_MAX_OPTIONS} options "
            "(`CHOICE_BLOCK_MIN_OPTIONS` / `CHOICE_BLOCK_MAX_OPTIONS`)."
        ),
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )
    correct_option_id: UUID = Field(
        description=(
            "Id of the option the student must pick. Always one of "
            "`options[*].oid`. Authors only — stripped from the "
            "release-side public view sent to learners."
        ),
        examples=["c1d2e3f4-5678-4abc-9012-3456789abcde"],
    )

    @classmethod
    def from_view(cls, view: SingleChoiceBlockView) -> Self:
        return cls(
            type=BlockType.SINGLE_CHOICE,
            oid=view.oid,
            position=view.position,
            options=[ChoiceOptionSchema.from_view(o) for o in view.options],
            correct_option_id=UUID(view.correct_option_id),
        )


class MultiChoiceBlockSchema(BaseModel):
    """Multi-choice answer block projection (authoring-side, read-only)."""

    type: Literal[BlockType.MULTI_CHOICE] = Field(
        default=BlockType.MULTI_CHOICE,
        description="Discriminator — always `multi_choice` for this schema.",
    )
    oid: UUID = Field(examples=["e1f2a3b4-5c6d-4e7f-8a90-1b2c3d4e5f60"])
    position: int = Field(examples=[3])
    options: list[ChoiceOptionSchema] = Field(
        description=(
            f"Between {CHOICE_BLOCK_MIN_OPTIONS} and "
            f"{CHOICE_BLOCK_MAX_OPTIONS} options."
        ),
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )
    correct_option_ids: list[UUID] = Field(
        description=(
            "Subset of `options[*].oid` the student must pick — "
            "order does not matter, set semantics. Authors only."
        ),
        min_length=1,
    )

    @classmethod
    def from_view(cls, view: MultiChoiceBlockView) -> Self:
        return cls(
            type=BlockType.MULTI_CHOICE,
            oid=view.oid,
            position=view.position,
            options=[ChoiceOptionSchema.from_view(o) for o in view.options],
            correct_option_ids=[UUID(o) for o in view.correct_option_ids],
        )


class TextInputBlockSchema(BaseModel):
    """Free-text answer block projection (authoring-side, read-only).

    Like the choice schemas, this exposes the accepted answers
    because the projection is for authors. The student-facing
    public view drops the answer list.
    """

    type: Literal[BlockType.TEXT_INPUT] = Field(
        default=BlockType.TEXT_INPUT,
        description="Discriminator — always `text_input` for this schema.",
    )
    oid: UUID = Field(examples=["f1a2b3c4-5d6e-4f70-8192-3a4b5c6d7e8f"])
    position: int = Field(examples=[4])
    accepted_answers: list[str] = Field(
        description=(
            "Author-provided list of accepted answers. Comparison "
            "happens at check-time under the block's own "
            "normalisation flags. Max "
            f"{TEXT_INPUT_MAX_ACCEPTED} entries "
            f"(`TEXT_INPUT_MAX_ACCEPTED`), each up to "
            f"{TEXT_INPUT_ANSWER_MAX_LEN} chars "
            "(`TEXT_INPUT_ANSWER_MAX_LEN`). Authors only."
        ),
        min_length=TEXT_INPUT_MIN_ACCEPTED,
        max_length=TEXT_INPUT_MAX_ACCEPTED,
    )
    case_sensitive: bool = Field(
        description=(
            "If true, the student's answer must match casing exactly."
        ),
        examples=[False],
    )
    trim_whitespace: bool = Field(
        description=(
            "If true, surrounding whitespace is stripped from both "
            "sides before comparison."
        ),
        examples=[True],
    )

    @classmethod
    def from_view(cls, view: TextInputBlockView) -> Self:
        return cls(
            type=BlockType.TEXT_INPUT,
            oid=view.oid,
            position=view.position,
            accepted_answers=list(view.accepted_answers),
            case_sensitive=view.case_sensitive,
            trim_whitespace=view.trim_whitespace,
        )


class FileBlockSchema(BaseModel):
    """Generic-file lesson-block projection (authoring-side, read-only).

    ``file`` is nullable: the FK is ``ON DELETE SET NULL`` on both
    draft and release tables, so a block whose backing file was
    purged degrades to a "file missing" placeholder rather than
    disappearing. When present, the nested :class:`FileSchema`
    already carries a short-lived presigned URL — the SPA renders
    download/preview affordance directly without a follow-up
    file-fetch endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    type: Literal[BlockType.FILE] = Field(
        default=BlockType.FILE,
        description="Discriminator — always `file` for this schema.",
    )
    oid: UUID
    position: int
    file: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved backing file with a short-lived presigned URL, "
            "or `null` if the file was deleted after the block was "
            "created."
        ),
    )
    title: str | None = Field(
        default=None,
        description=(
            "Optional caption shown next to the file link. "
            f"Max {BLOCK_TITLE_MAX_LEN} chars (`BLOCK_TITLE_MAX_LEN`)."
        ),
        max_length=BLOCK_TITLE_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: FileBlockView) -> Self:
        return cls.model_validate(view)


class VideoFileBlockSchema(BaseModel):
    """Uploaded-video lesson-block projection.

    Sibling of :class:`RutubeVideoBlockSchema` — same playback
    intent, different provider. The nested :class:`FileSchema`
    carries a short-lived presigned URL the SPA's video player
    can plug straight into ``<video src>`` (or our
    :class:`VideoPlayer` wrapper).
    """

    model_config = ConfigDict(from_attributes=True)

    type: Literal[BlockType.VIDEO_FILE] = Field(
        default=BlockType.VIDEO_FILE,
        description="Discriminator — always `video_file` for this schema.",
    )
    oid: UUID
    position: int
    file: FileSchema | None = Field(default=None)
    title: str | None = Field(
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: VideoFileBlockView) -> Self:
        return cls.model_validate(view)


class CollageItemSchema(BaseModel):
    """One photo inside a :class:`PhotoCollageBlockSchema`."""

    model_config = ConfigDict(from_attributes=True)

    file: FileSchema | None = Field(
        default=None,
        description=(
            "Resolved backing image with a short-lived presigned URL, "
            "or `null` if the file was deleted."
        ),
    )
    caption: str | None = Field(
        default=None,
        description=(
            "Optional short caption under the photo. "
            f"Max {PHOTO_COLLAGE_CAPTION_MAX_LEN} chars "
            "(`PHOTO_COLLAGE_CAPTION_MAX_LEN`)."
        ),
        max_length=PHOTO_COLLAGE_CAPTION_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: CollageItemView) -> Self:
        return cls.model_validate(view)


class PhotoCollageBlockSchema(BaseModel):
    """Photo-collage lesson-block projection.

    Holds a bounded list of ``(file_id, caption)`` items — between
    ``PHOTO_COLLAGE_MIN_ITEMS`` and ``PHOTO_COLLAGE_MAX_ITEMS``. The
    "each item is an image" content-type invariant is enforced at
    the command-handler boundary on add/update, not at the schema
    layer.
    """

    type: Literal[BlockType.PHOTO_COLLAGE] = Field(
        default=BlockType.PHOTO_COLLAGE,
        description="Discriminator — always `photo_collage`.",
    )
    oid: UUID
    position: int
    items: list[CollageItemSchema] = Field(
        description=(
            f"Between {PHOTO_COLLAGE_MIN_ITEMS} and "
            f"{PHOTO_COLLAGE_MAX_ITEMS} photos."
        ),
        min_length=PHOTO_COLLAGE_MIN_ITEMS,
        max_length=PHOTO_COLLAGE_MAX_ITEMS,
    )
    title: str | None = Field(
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
    )

    @classmethod
    def from_view(cls, view: PhotoCollageBlockView) -> Self:
        return cls(
            type=BlockType.PHOTO_COLLAGE,
            oid=view.oid,
            position=view.position,
            items=[CollageItemSchema.from_view(it) for it in view.items],
            title=view.title,
        )


_LessonBlockSchemaUnion = (
    HtmlBlockSchema
    | KatexBlockSchema
    | RutubeVideoBlockSchema
    | CodeBlockSchema
    | SingleChoiceBlockSchema
    | MultiChoiceBlockSchema
    | TextInputBlockSchema
    | FileBlockSchema
    | VideoFileBlockSchema
    | PhotoCollageBlockSchema
)

LessonBlockSchema = Annotated[_LessonBlockSchemaUnion, Discriminator("type")]


def _block_view_to_schema(view: LessonBlockView) -> _LessonBlockSchemaUnion:
    if isinstance(view, HtmlBlockView):
        return HtmlBlockSchema.from_view(view)
    if isinstance(view, KatexBlockView):
        return KatexBlockSchema.from_view(view)
    if isinstance(view, CodeBlockView):
        return CodeBlockSchema.from_view(view)
    if isinstance(view, SingleChoiceBlockView):
        return SingleChoiceBlockSchema.from_view(view)
    if isinstance(view, MultiChoiceBlockView):
        return MultiChoiceBlockSchema.from_view(view)
    if isinstance(view, TextInputBlockView):
        return TextInputBlockSchema.from_view(view)
    if isinstance(view, FileBlockView):
        return FileBlockSchema.from_view(view)
    if isinstance(view, VideoFileBlockView):
        return VideoFileBlockSchema.from_view(view)
    if isinstance(view, PhotoCollageBlockView):
        return PhotoCollageBlockSchema.from_view(view)
    return RutubeVideoBlockSchema.from_view(view)


class CourseDraftLessonSchema(BaseModel):
    """Lesson projection inside the draft tree."""

    oid: UUID = Field(examples=["b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e"])
    title: str = Field(examples=["Урок 1: Введение"])
    position: int = Field(examples=[0])
    blocks: list[LessonBlockSchema] = Field(
        description=(
            "Lesson content blocks ordered by position ascending. "
            "Discriminated union over `type`."
        ),
    )

    @classmethod
    def from_view(cls, view: DraftLessonView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            position=view.position,
            blocks=[_block_view_to_schema(b) for b in view.blocks],
        )


class CourseDraftModuleSchema(BaseModel):
    """Module projection inside the draft tree."""

    oid: UUID = Field(examples=["a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d"])
    title: str = Field(examples=["Введение"])
    description: str | None = Field(examples=["Обзор курса.", None])
    position: int = Field(examples=[0])
    lessons: list[CourseDraftLessonSchema]

    @classmethod
    def from_view(cls, view: DraftModuleView) -> Self:
        return cls(
            oid=view.oid,
            title=view.title,
            description=view.description,
            position=view.position,
            lessons=[CourseDraftLessonSchema.from_view(ls) for ls in view.lessons],
        )


class CourseDraftSchema(BaseModel):
    """Full draft tree response for ``GET /courses/{course_id}/content/draft``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "course_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "modules": [
                        {
                            "oid": "a1b2c3d4-5e6f-4a8b-9c0d-1e2f3a4b5c6d",
                            "title": "Введение",
                            "description": "Обзор курса.",
                            "position": 0,
                            "lessons": [
                                {
                                    "oid": "b2c3d4e5-6f7a-4b8c-9d0e-2f3a4b5c6d7e",
                                    "title": "Урок 1",
                                    "position": 0,
                                    "blocks": [
                                        {
                                            "type": "html",
                                            "oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                                            "position": 0,
                                            "html": "<p>Welcome.</p>",
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                    "fetched_at": "2026-05-01T10:00:00+00:00",
                },
            ],
        },
    )

    course_id: UUID
    modules: list[CourseDraftModuleSchema]
    fetched_at: datetime

    @classmethod
    def from_view(cls, view: CourseDraftView, fetched_at: datetime) -> Self:
        return cls(
            course_id=view.product_id,
            modules=[CourseDraftModuleSchema.from_view(m) for m in view.modules],
            fetched_at=fetched_at,
        )


# ============================== routes — modules ============================== #


_COURSE_AUTHOR_MAP = AUTHENTICATED_OWNER_FIELD_MAP | {
    ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE,
}


@router.post(
    "/{course_id}/modules",
    summary="Add a module to a course product",
    operation_id="addCourseModule",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedCourseModuleSchema,
    error_map=_COURSE_AUTHOR_MAP,
)
async def add_module(
    request: Request,
    payload: AddCourseModuleSchema,
    interactor: FromDishka[AddCourseModuleCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> CreatedCourseModuleSchema:
    """Append a module to the course's draft. Author-only.

    Args:
        request: Source of the access cookie.
        payload: Module fields validated by ``AddCourseModuleSchema``.
        interactor: Injected add-module handler.
        auth: Injected authenticator.
        course_id: Course product's UUID.

    Returns:
        ``201 Created`` with the new module's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403 — caller isn't the course author.
        EntityNotFoundError: HTTP 404 — course doesn't exist.
        ProductDoesNotSupportError: HTTP 409 — product is not a course.
        FieldError: HTTP 422 — VO invariants violated.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddCourseModuleCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
            title=payload.title,
            description=payload.description,
        ),
    )
    return CreatedCourseModuleSchema(oid=oid)


@router.patch(
    "/{course_id}/modules/{module_id}/title",
    summary="Rename a module",
    operation_id="renameCourseModule",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def rename_module(
    request: Request,
    payload: RenameCourseModuleSchema,
    interactor: FromDishka[RenameCourseModuleCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    module_id: Annotated[UUID, _MODULE_ID_PATH],
) -> None:
    """Replace the module's title.

    Args:
        request: Access cookie source.
        payload: ``{"title": "..."}`` validated by ``RenameCourseModuleSchema``.
        interactor: Injected rename handler.
        auth: Injected authenticator.
        course_id: Course product's UUID (for URL clarity; ownership
            is verified via ``module.product_id``).
        module_id: Target module UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — module or product not found.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        RenameCourseModuleCommand(
            actor_id=ctx.user_id,
            module_id=CourseModuleID(module_id),
            title=payload.title,
        ),
    )


@router.patch(
    "/{course_id}/modules/{module_id}/description",
    summary="Update or clear a module's description",
    operation_id="updateCourseModuleDescription",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_module_description(
    request: Request,
    payload: UpdateCourseModuleDescriptionSchema,
    interactor: FromDishka[UpdateCourseModuleDescriptionCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    module_id: Annotated[UUID, _MODULE_ID_PATH],
) -> None:
    """Set or clear the module's description.

    Args:
        request: Access cookie source.
        payload: ``{"description": "..."}`` or ``{"description": null}``.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product's UUID.
        module_id: Target module UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCourseModuleDescriptionCommand(
            actor_id=ctx.user_id,
            module_id=CourseModuleID(module_id),
            description=payload.description,
        ),
    )


@router.put(
    "/{course_id}/modules/order",
    summary="Replace module ordering atomically",
    operation_id="reorderCourseModules",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {InvalidReorderError: INVALID_REORDER_RULE},
)
async def reorder_modules(
    request: Request,
    payload: ReorderCourseModulesSchema,
    interactor: FromDishka[ReorderCourseModulesCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> None:
    """Set module ordering by full list of ids.

    Args:
        request: Access cookie source.
        payload: ``{"ordered_ids": [...]}`` — full module list of the course.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product's UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — product not found.
        InvalidReorderError: HTTP 409 — ``ordered_ids`` doesn't match
            the existing module set.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ReorderCourseModulesCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
            ordered_ids=[CourseModuleID(oid) for oid in payload.ordered_ids],
        ),
    )


@router.delete(
    "/{course_id}/modules/{module_id}",
    summary="Delete a module (cascades to its lessons)",
    operation_id="deleteCourseModule",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_module(
    request: Request,
    interactor: FromDishka[DeleteCourseModuleCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    module_id: Annotated[UUID, _MODULE_ID_PATH],
) -> None:
    """Hard-delete the module. Cascades to lessons via FK.

    Args:
        request: Access cookie source.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product's UUID.
        module_id: Target module UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteCourseModuleCommand(
            actor_id=ctx.user_id,
            module_id=CourseModuleID(module_id),
        ),
    )


# ============================== routes — lessons ============================== #


@router.post(
    "/{course_id}/modules/{module_id}/lessons",
    summary="Add a lesson to a module",
    operation_id="addCourseLesson",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedCourseLessonSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_lesson(
    request: Request,
    payload: AddCourseLessonSchema,
    interactor: FromDishka[AddCourseLessonCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    module_id: Annotated[UUID, _MODULE_ID_PATH],
) -> CreatedCourseLessonSchema:
    """Append a lesson to the module. Author-only.

    Args:
        request: Access cookie source.
        payload: Lesson fields validated by ``AddCourseLessonSchema``.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product's UUID.
        module_id: Target module UUID.

    Returns:
        ``201 Created`` with the new lesson's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddCourseLessonCommand(
            actor_id=ctx.user_id,
            module_id=CourseModuleID(module_id),
            title=payload.title,
        ),
    )
    return CreatedCourseLessonSchema(oid=oid)


@router.patch(
    "/{course_id}/lessons/{lesson_id}/title",
    summary="Rename a lesson",
    operation_id="renameCourseLesson",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def rename_lesson(
    request: Request,
    payload: RenameCourseLessonSchema,
    interactor: FromDishka[RenameCourseLessonCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> None:
    """Replace the lesson's title.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        RenameCourseLessonCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            title=payload.title,
        ),
    )


@router.patch(
    "/{course_id}/lessons/{lesson_id}/move",
    summary="Move a lesson to another module within the same course",
    operation_id="moveCourseLesson",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {CrossCourseLessonMoveError: CROSS_COURSE_LESSON_MOVE_RULE},
)
async def move_lesson(
    request: Request,
    payload: MoveCourseLessonSchema,
    interactor: FromDishka[MoveCourseLessonCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> None:
    """Move the lesson to ``target_module_id`` (must belong to the same course).

    The lesson is appended to the end of the target module — apply
    a follow-up reorder to place it precisely.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — lesson or target module not found.
        CrossCourseLessonMoveError: HTTP 409 — target module belongs
            to a different course.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        MoveCourseLessonCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            target_module_id=CourseModuleID(payload.target_module_id),
        ),
    )


@router.put(
    "/{course_id}/modules/{module_id}/lessons/order",
    summary="Replace lesson ordering inside a module atomically",
    operation_id="reorderCourseLessons",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {InvalidReorderError: INVALID_REORDER_RULE},
)
async def reorder_lessons(
    request: Request,
    payload: ReorderCourseLessonsSchema,
    interactor: FromDishka[ReorderCourseLessonsCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    module_id: Annotated[UUID, _MODULE_ID_PATH],
) -> None:
    """Set lesson ordering inside a module by full list of ids.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — module not found.
        InvalidReorderError: HTTP 409 — ids don't match existing lessons.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        ReorderCourseLessonsCommand(
            actor_id=ctx.user_id,
            module_id=CourseModuleID(module_id),
            ordered_ids=[CourseLessonID(oid) for oid in payload.ordered_ids],
        ),
    )


@router.delete(
    "/{course_id}/lessons/{lesson_id}",
    summary="Delete a lesson",
    operation_id="deleteCourseLesson",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_lesson(
    request: Request,
    interactor: FromDishka[DeleteCourseLessonCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> None:
    """Hard-delete the lesson. Cascades to its blocks via FK.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteCourseLessonCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
        ),
    )


# ============================== routes — read ============================== #


@router.get(
    "/{course_id}/content/draft",
    summary="Read the full draft tree of a course",
    operation_id="getCourseDraft",
    response_model=CourseDraftSchema,
    dependencies=_AUTH_SECURITY,
    error_map=_COURSE_AUTHOR_MAP,
)
async def get_draft(
    request: Request,
    interactor: FromDishka[GetCourseDraftQueryHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> CourseDraftSchema:
    """Return the full draft tree of the course (modules + lessons + blocks).

    Caller needs ``READ_PRODUCT`` on the product (owner or any
    collaborator with that permission). Each lesson carries an
    ordered list of typed blocks (``html`` / ``katex`` /
    ``rutube_video``) under a discriminated union on ``type``.

    Returns:
        :class:`CourseDraftSchema` with modules ordered by position,
        each carrying its lessons (also ordered by position) and
        their blocks (ordered by position).

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller has no
            collaboration with ``READ_PRODUCT``.
        EntityNotFoundError: HTTP 404 — course not found.
        ProductDoesNotSupportError: HTTP 409 — product is not a course.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetCourseDraftQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
        ),
    )
    return CourseDraftSchema.from_view(
        view,
        fetched_at=datetime.now(timezone.utc),
    )


# ============================== schemas — blocks ============================== #


_BLOCK_ID_PATH: Final = Path(
    description="Target lesson-block's UUID.",
    examples=["c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"],
)


class AddHtmlBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/html``.

    Incoming HTML is sanitized server-side; unsafe tags and
    attributes are stripped before reaching the domain.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"html": "<p>Hello</p>"}]},
    )

    html: str = Field(
        description=(
            "Raw HTML body of the block. Sanitized server-side; "
            f"length limit is {HTML_BLOCK_MAX_LEN} chars "
            "(`HTML_BLOCK_MAX_LEN`) measured **after** sanitization. "
            "Empty payload is accepted — the author fills the body "
            "in the editor after creating the block."
        ),
        max_length=HTML_BLOCK_MAX_LEN,
        examples=["<p>Hello</p>"],
    )


class UpdateHtmlBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/html``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"html": "<p>Updated</p>"}]},
    )

    html: str = Field(
        description=(
            "New raw HTML body. Sanitized server-side; max length "
            f"{HTML_BLOCK_MAX_LEN} chars after sanitization. Empty "
            "payload is accepted (clears the body)."
        ),
        max_length=HTML_BLOCK_MAX_LEN,
        examples=["<p>Updated</p>"],
    )


class AddKatexBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/katex``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"source": r"\int_0^1 x^2\, dx"}],
        },
    )

    source: str = Field(
        description=(
            "KaTeX-compatible math source — a strict subset of LaTeX "
            "(see https://katex.org/docs/support_table.html). NOT "
            "sanitized server-side — KaTeX renders it safely on the "
            "client. "
            f"Max length {KATEX_BLOCK_MAX_LEN} chars "
            "(`KATEX_BLOCK_MAX_LEN`). Empty payload is accepted — "
            "the author fills the source in the editor after "
            "creating the block."
        ),
        max_length=KATEX_BLOCK_MAX_LEN,
        examples=[r"\int_0^1 x^2\, dx"],
    )


class UpdateKatexBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/katex``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"source": r"E = mc^2"}],
        },
    )

    source: str = Field(
        description=(
            f"New KaTeX source body. Max length {KATEX_BLOCK_MAX_LEN} "
            "chars. Empty payload is accepted (clears the source)."
        ),
        max_length=KATEX_BLOCK_MAX_LEN,
        examples=[r"E = mc^2"],
    )


class CodeTabPayload(BaseModel):
    """Per-tab payload for code-block create/update endpoints.

    Same shape as :class:`CodeTabSchema` but on the request side.
    Mirrors the domain :class:`CodeTabInput` directly.
    """

    label: str = Field(
        description=(
            f"Tab label, max {CODE_TAB_LABEL_MAX_LEN} chars. Empty "
            "string is only valid for single-tab blocks."
        ),
        max_length=CODE_TAB_LABEL_MAX_LEN,
        examples=["npm"],
    )
    source: str = Field(
        description=(f"Verbatim source. Max length {CODE_BLOCK_MAX_LEN} chars."),
        max_length=CODE_BLOCK_MAX_LEN,
        examples=["npm install react"],
    )
    language: CodeBlockLanguage = Field(
        description="Syntax-highlight language for this tab.",
        examples=[CodeBlockLanguage.BASH],
    )


_CODE_TABS_EXAMPLE: Final[Any] = [
    {"label": "npm", "source": "npm install react", "language": "bash"},
    {"label": "pnpm", "source": "pnpm add react", "language": "bash"},
    {"label": "yarn", "source": "yarn add react", "language": "bash"},
]


class AddCodeBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/code``.

    Sources are taken verbatim — no sanitization, no whitespace
    stripping. ``tabs`` must be non-empty and is capped at
    ``CODE_BLOCK_MAX_TABS``. Multi-tab blocks must have non-empty
    unique labels; single-tab blocks may have an empty label.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"tabs": _CODE_TABS_EXAMPLE}]},
    )

    tabs: list[CodeTabPayload] = Field(
        description=(
            "Code variants. At least one required, at most "
            f"{CODE_BLOCK_MAX_TABS} (`CODE_BLOCK_MAX_TABS`)."
        ),
        min_length=1,
        max_length=CODE_BLOCK_MAX_TABS,
    )


class UpdateCodeBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/code``.

    Replaces the entire tabs list. Partial / per-tab updates are
    intentionally not supported — see :class:`UpdateCodeBlockCommand`.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"tabs": _CODE_TABS_EXAMPLE}]},
    )

    tabs: list[CodeTabPayload] = Field(
        description="Full new tabs list — replaces the existing one.",
        min_length=1,
        max_length=CODE_BLOCK_MAX_TABS,
    )


class ChoiceOptionDraftPayload(BaseModel):
    """One option entry submitted by the author.

    ``label`` is plain text (max ``CHOICE_OPTION_LABEL_MAX_LEN``).
    ``is_correct`` flags whether this option counts as a correct
    answer — exactly one for single-choice blocks, at least one
    for multi-choice. The server mints option ids; ids are not
    accepted on input.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"label": "Paris", "is_correct": True}]},
    )

    label: str = Field(
        description=(
            "Plain-text option caption. "
            f"Max {CHOICE_OPTION_LABEL_MAX_LEN} chars "
            "(`CHOICE_OPTION_LABEL_MAX_LEN`). Empty / blank labels "
            "are accepted as placeholders the author fills in after "
            "creating the block — uniqueness only applies to labels "
            "with actual text."
        ),
        max_length=CHOICE_OPTION_LABEL_MAX_LEN,
        examples=["Paris"],
    )
    is_correct: bool = Field(
        description=(
            "If true, the student must pick this option for the "
            "answer to count as correct."
        ),
        examples=[False],
    )


_CHOICE_OPTIONS_EXAMPLE: Final[Any] = [
    {"label": "Paris", "is_correct": True},
    {"label": "Berlin", "is_correct": False},
    {"label": "Madrid", "is_correct": False},
]
_MULTI_CHOICE_OPTIONS_EXAMPLE: Final[Any] = [
    {"label": "Python", "is_correct": True},
    {"label": "Rust", "is_correct": True},
    {"label": "PHP", "is_correct": False},
]


class AddSingleChoiceBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/single-choice``.

    Submit between ``CHOICE_BLOCK_MIN_OPTIONS`` and
    ``CHOICE_BLOCK_MAX_OPTIONS`` options; exactly one must carry
    ``is_correct: true``. Sending zero or more than one correct
    option yields HTTP 422.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"options": _CHOICE_OPTIONS_EXAMPLE}]},
    )

    options: list[ChoiceOptionDraftPayload] = Field(
        description=(
            f"Between {CHOICE_BLOCK_MIN_OPTIONS} and "
            f"{CHOICE_BLOCK_MAX_OPTIONS} options "
            "(`CHOICE_BLOCK_MIN_OPTIONS` / `CHOICE_BLOCK_MAX_OPTIONS`). "
            "Exactly one must have `is_correct=true`."
        ),
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )


class UpdateSingleChoiceBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/single-choice``.

    Replaces the entire option list. Per-option partial updates are
    intentionally unsupported — see ``UpdateSingleChoiceBlockCommand``.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"options": _CHOICE_OPTIONS_EXAMPLE}]},
    )

    options: list[ChoiceOptionDraftPayload] = Field(
        description="Full new option list — replaces the existing one.",
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )


class AddMultiChoiceBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/multi-choice``.

    At least one option must have ``is_correct=true``. The student
    must pick exactly the flagged set — order does not matter.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"options": _MULTI_CHOICE_OPTIONS_EXAMPLE}],
        },
    )

    options: list[ChoiceOptionDraftPayload] = Field(
        description=(
            f"Between {CHOICE_BLOCK_MIN_OPTIONS} and "
            f"{CHOICE_BLOCK_MAX_OPTIONS} options. At least one "
            "must have `is_correct=true`."
        ),
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )


class UpdateMultiChoiceBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/multi-choice``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"options": _MULTI_CHOICE_OPTIONS_EXAMPLE}],
        },
    )

    options: list[ChoiceOptionDraftPayload] = Field(
        description="Full new option list — replaces the existing one.",
        min_length=CHOICE_BLOCK_MIN_OPTIONS,
        max_length=CHOICE_BLOCK_MAX_OPTIONS,
    )


_TEXT_INPUT_EXAMPLE: Final[Any] = {
    "accepted_answers": ["Paris", "paris"],
    "case_sensitive": False,
    "trim_whitespace": True,
}


class AddTextInputBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/text-input``.

    Submit a non-empty list of accepted-answer strings plus the two
    normalisation flags. Comparison at check-time normalises both
    sides under those flags, so toggling them later can't silently
    introduce duplicates (the entity validates uniqueness under the
    active normalisation).
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [_TEXT_INPUT_EXAMPLE]},
    )

    accepted_answers: list[str] = Field(
        description=(
            f"Between {TEXT_INPUT_MIN_ACCEPTED} and "
            f"{TEXT_INPUT_MAX_ACCEPTED} accepted answers "
            "(`TEXT_INPUT_MIN_ACCEPTED` / `TEXT_INPUT_MAX_ACCEPTED`). "
            f"Each up to {TEXT_INPUT_ANSWER_MAX_LEN} chars "
            "(`TEXT_INPUT_ANSWER_MAX_LEN`)."
        ),
        min_length=TEXT_INPUT_MIN_ACCEPTED,
        max_length=TEXT_INPUT_MAX_ACCEPTED,
    )
    case_sensitive: bool = Field(
        description=(
            "If true, comparison preserves casing; if false, both "
            "sides are case-folded before matching."
        ),
        examples=[False],
    )
    trim_whitespace: bool = Field(
        description=(
            "If true, surrounding whitespace is stripped from both "
            "sides before matching."
        ),
        examples=[True],
    )


class UpdateTextInputBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/text-input``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [_TEXT_INPUT_EXAMPLE]},
    )

    accepted_answers: list[str] = Field(
        description="Full new accepted-answer list — replaces the existing one.",
        min_length=TEXT_INPUT_MIN_ACCEPTED,
        max_length=TEXT_INPUT_MAX_ACCEPTED,
    )
    case_sensitive: bool
    trim_whitespace: bool


class ReorderLessonBlocksSchema(BaseModel):
    """Body for ``PUT /courses/{course_id}/lessons/{lesson_id}/blocks/order``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ordered_ids": [
                        "d4e5f6a7-8b9c-4d0e-1f2a-4b5c6d7e8f9a",
                        "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
                    ],
                },
            ],
        },
    )

    ordered_ids: list[UUID] = Field(
        description=(
            "Full list of block ids inside the lesson in the "
            "desired order. Must match the existing block set "
            "exactly (any types). HTML, KaTeX and Rutube blocks share one "
            "position-space within a lesson."
        ),
        examples=[
            [
                "d4e5f6a7-8b9c-4d0e-1f2a-4b5c6d7e8f9a",
                "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f",
            ],
        ],
    )


class CreatedLessonBlockSchema(BaseModel):
    """Response for block-creation endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created block.",
        examples=["c3d4e5f6-7a8b-4c9d-0e1f-3a4b5c6d7e8f"],
    )


# ============================== routes — blocks ============================== #


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/html",
    summary="Add an HTML block to a lesson",
    operation_id="addHtmlBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_html_block(
    request: Request,
    payload: AddHtmlBlockSchema,
    interactor: FromDishka[AddHtmlBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append an HTML block to the lesson. Author-only.

    Args:
        request: Source of the access cookie.
        payload: Raw HTML body (sanitized server-side).
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID (for URL clarity).
        lesson_id: Target lesson UUID.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422 — sanitized HTML empty or too long.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddHtmlBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            html=payload.html,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/katex",
    summary="Add a KaTeX block to a lesson",
    operation_id="addKatexBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_katex_block(
    request: Request,
    payload: AddKatexBlockSchema,
    interactor: FromDishka[AddKatexBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a KaTeX block to the lesson. Author-only.

    Args:
        request: Source of the access cookie.
        payload: Raw KaTeX-compatible math source.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID.
        lesson_id: Target lesson UUID.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddKatexBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            source=payload.source,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/html",
    summary="Replace an HTML block's body",
    operation_id="updateHtmlBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_html_block(
    request: Request,
    payload: UpdateHtmlBlockSchema,
    interactor: FromDishka[UpdateHtmlBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the HTML body of an existing block.

    Args:
        request: Access cookie source.
        payload: New raw HTML (sanitized server-side).
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID.
        block_id: Target block UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't of type `html`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateHtmlBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            html=payload.html,
        ),
    )


@router.patch(
    "/{course_id}/blocks/{block_id}/katex",
    summary="Replace a KaTeX block's source",
    operation_id="updateKatexBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_katex_block(
    request: Request,
    payload: UpdateKatexBlockSchema,
    interactor: FromDishka[UpdateKatexBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the KaTeX source of an existing block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't of type `katex`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateKatexBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            source=payload.source,
        ),
    )


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/code",
    summary="Add a code block to a lesson",
    operation_id="addCodeBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_code_block(
    request: Request,
    payload: AddCodeBlockSchema,
    interactor: FromDishka[AddCodeBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a source-code block to the lesson. Author-only.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422 — language unsupported or source too long.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddCodeBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            tabs=tuple(
                CodeTabInput(
                    label=t.label,
                    source=t.source,
                    language=t.language.value,
                )
                for t in payload.tabs
            ),
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/code",
    summary="Replace a code block's source and language",
    operation_id="updateCodeBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_code_block(
    request: Request,
    payload: UpdateCodeBlockSchema,
    interactor: FromDishka[UpdateCodeBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the body of an existing code block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't of type `code`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCodeBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            tabs=tuple(
                CodeTabInput(
                    label=t.label,
                    source=t.source,
                    language=t.language.value,
                )
                for t in payload.tabs
            ),
        ),
    )


def _to_choice_inputs(
    options: list[ChoiceOptionDraftPayload],
) -> tuple[ChoiceOptionDraftInput, ...]:
    return tuple(
        ChoiceOptionDraftInput(label=o.label, is_correct=o.is_correct)
        for o in options
    )


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/single-choice",
    summary="Add a single-choice answer block to a lesson",
    operation_id="addSingleChoiceBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_single_choice_block(
    request: Request,
    payload: AddSingleChoiceBlockSchema,
    interactor: FromDishka[AddSingleChoiceBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a single-choice answer block to the lesson. Author-only.

    The block carries only the answer field — the question prompt
    is authored as a preceding HTML block. Exactly one option must
    have ``is_correct=true``; zero or more than one yields 422.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422 — invalid options or correct-count.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddSingleChoiceBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            options=_to_choice_inputs(payload.options),
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/single-choice",
    summary="Replace a single-choice block's options and correct answer",
    operation_id="updateSingleChoiceBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_single_choice_block(
    request: Request,
    payload: UpdateSingleChoiceBlockSchema,
    interactor: FromDishka[UpdateSingleChoiceBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the option list of an existing single-choice block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't `single_choice`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateSingleChoiceBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            options=_to_choice_inputs(payload.options),
        ),
    )


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/multi-choice",
    summary="Add a multi-choice answer block to a lesson",
    operation_id="addMultiChoiceBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_multi_choice_block(
    request: Request,
    payload: AddMultiChoiceBlockSchema,
    interactor: FromDishka[AddMultiChoiceBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a multi-choice answer block to the lesson. Author-only.

    At least one option must have ``is_correct=true``. The student
    must pick exactly the flagged set — order does not matter.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddMultiChoiceBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            options=_to_choice_inputs(payload.options),
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/multi-choice",
    summary="Replace a multi-choice block's options and correct-answer set",
    operation_id="updateMultiChoiceBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_multi_choice_block(
    request: Request,
    payload: UpdateMultiChoiceBlockSchema,
    interactor: FromDishka[UpdateMultiChoiceBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the option list of an existing multi-choice block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't `multi_choice`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateMultiChoiceBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            options=_to_choice_inputs(payload.options),
        ),
    )


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/text-input",
    summary="Add a free-text answer block to a lesson",
    operation_id="addTextInputBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_text_input_block(
    request: Request,
    payload: AddTextInputBlockSchema,
    interactor: FromDishka[AddTextInputBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a free-text answer block to the lesson. Author-only.

    The student types an answer into a single-line input; the
    server compares against ``accepted_answers`` under the
    configured normalisation flags.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422 — empty / too-long / duplicate answer.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddTextInputBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            accepted_answers=tuple(payload.accepted_answers),
            case_sensitive=payload.case_sensitive,
            trim_whitespace=payload.trim_whitespace,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/text-input",
    summary="Replace a text-input block's accepted answers and flags",
    operation_id="updateTextInputBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_text_input_block(
    request: Request,
    payload: UpdateTextInputBlockSchema,
    interactor: FromDishka[UpdateTextInputBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the accepted answers and normalisation flags.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't `text_input`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateTextInputBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            accepted_answers=tuple(payload.accepted_answers),
            case_sensitive=payload.case_sensitive,
            trim_whitespace=payload.trim_whitespace,
        ),
    )


@router.put(
    "/{course_id}/lessons/{lesson_id}/blocks/order",
    summary="Replace block ordering inside a lesson atomically",
    operation_id="reorderLessonBlocks",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {InvalidReorderError: INVALID_REORDER_RULE},
)
async def reorder_lesson_blocks(
    request: Request,
    payload: ReorderLessonBlocksSchema,
    interactor: FromDishka[ReorderLessonBlocksCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> None:
    """Replace block ordering inside a lesson by full list of ids.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404 — lesson not found.
        InvalidReorderError: HTTP 409 — ids don't match existing blocks.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        ReorderLessonBlocksCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            ordered_ids=[LessonBlockID(oid) for oid in payload.ordered_ids],
        ),
    )


@router.delete(
    "/{course_id}/blocks/{block_id}",
    summary="Delete a lesson block",
    operation_id="deleteLessonBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_lesson_block(
    request: Request,
    interactor: FromDishka[DeleteLessonBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Hard-delete the block. Child rows cascade via FK.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteLessonBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
        ),
    )


# ============================== schemas — Rutube video block ============================== #


class AddRutubeVideoBlockSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/lessons/{lesson_id}/blocks/rutube-video``.

    The server parses the Rutube URL into a 32-char hex id;
    ``embed_url`` is computed at read time. ``title`` is optional.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "rutube_url": (
                        "https://rutube.ru/video/f9bb1e0bdfac28c93c2c35a45f87f3eb/"
                    ),
                    "title": "Lecture 1: Introduction",
                },
            ],
        },
    )

    rutube_url: str = Field(
        description=(
            "Rutube video URL of the form "
            "`https://rutube.ru/video/{32-hex-id}/`. The server "
            "extracts the id and rejects any other host (HTTP 422 "
            "`InvalidRutubeUrl`)."
        ),
        examples=[
            "https://rutube.ru/video/f9bb1e0bdfac28c93c2c35a45f87f3eb/",
        ],
    )
    title: str | None = Field(
        default=None,
        description=(
            f"Optional caption. Max length {VIDEO_TITLE_MAX_LEN} chars "
            "(`VIDEO_TITLE_MAX_LEN`); omit or `null` to leave empty."
        ),
        min_length=1,
        max_length=VIDEO_TITLE_MAX_LEN,
        examples=["Lecture 1: Introduction", None],
    )


class UpdateRutubeVideoBlockSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/blocks/{block_id}/rutube-video``.

    ``rutube_url`` is required. ``title`` is required to be set
    explicitly: ``null`` clears the caption, a string sets it.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "rutube_url": (
                        "https://rutube.ru/video/0123456789abcdef0123456789abcdef/"
                    ),
                    "title": "Updated caption",
                },
            ],
        },
    )

    rutube_url: str = Field(
        description="New Rutube video URL — must match the same format as add.",
        examples=[
            "https://rutube.ru/video/0123456789abcdef0123456789abcdef/",
        ],
    )
    title: str | None = Field(
        description=(
            f"New caption, or `null` to clear. Max length {VIDEO_TITLE_MAX_LEN} chars."
        ),
        min_length=1,
        max_length=VIDEO_TITLE_MAX_LEN,
        examples=["Updated caption", None],
    )


# ============================== routes — Rutube video block ============================== #


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/rutube-video",
    summary="Add a Rutube video block to a lesson",
    operation_id="addRutubeVideoBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_rutube_video_block(
    request: Request,
    payload: AddRutubeVideoBlockSchema,
    interactor: FromDishka[AddRutubeVideoBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
) -> CreatedLessonBlockSchema:
    """Append a Rutube video block to the lesson. Author-only.

    Args:
        request: Source of the access cookie.
        payload: Rutube URL + optional caption.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Course product UUID.
        lesson_id: Target lesson UUID.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: HTTP 422 — bad Rutube URL or title VO violation.
    """
    del course_id
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        AddRutubeVideoBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            rutube_url=payload.rutube_url,
            title=payload.title,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/rutube-video",
    summary="Replace a Rutube video block's URL and caption",
    operation_id="updateRutubeVideoBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE},
)
async def update_rutube_video_block(
    request: Request,
    payload: UpdateRutubeVideoBlockSchema,
    interactor: FromDishka[UpdateRutubeVideoBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
) -> None:
    """Replace the Rutube URL and caption of an existing Rutube video block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't of type `rutube_video`.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateRutubeVideoBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            rutube_url=payload.rutube_url,
            title=payload.title,
        ),
    )


# ============================== routes — File / VideoFile / PhotoCollage ============================== #
# Multipart endpoints: the file IS the request body. No Pydantic body
# schema — fields come in as ``UploadFile`` (the binary part) plus
# ``Form(...)`` companions (title, captions). Bounds (max-length on
# title, max-length on caption, item count for collage) ride on the
# ``Form(...)`` defaults; the corresponding entity-side invariants
# in ``BlockTitle`` / ``CollageCaption`` / ``PhotoCollageBlock`` are
# the source of truth and re-validate server-side anyway.


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/file",
    summary="Upload a file and append a generic-file block to a lesson",
    operation_id="addFileBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {StorageQuotaExceededError: STORAGE_QUOTA_EXCEEDED_RULE},
)
async def add_file_block(
    request: Request,
    interactor: FromDishka[AddFileBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
    file: UploadFile = File(  # noqa: B008
        description="The file bytes; any content type is accepted.",
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description=(
            "Optional caption shown above the file. Max "
            f"{BLOCK_TITLE_MAX_LEN} chars (`BLOCK_TITLE_MAX_LEN`)."
        ),
    ),
) -> CreatedLessonBlockSchema:
    """Upload bytes, append a generic-file block to the lesson. Author-only.

    Args:
        request: Source of the access cookie.
        interactor: Injected add-file-block handler.
        auth: Injected authenticator.
        course_id: Course product UUID (framing only — handler authorises
            on the lesson's denormalised product id).
        lesson_id: Target lesson UUID.
        file: ``multipart/form-data`` field ``file`` carrying the
            bytes. Capped at ``LESSON_FILE_BLOCK_MAX_BYTES``.
        title: ``multipart/form-data`` field ``title``; optional.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        StorageQuotaExceededError: HTTP 413 — upload would exceed plan cap.
        FieldError: HTTP 422 — title VO violation or file too large.
    """
    del course_id
    ctx = await auth.authenticate(request)
    data, content_type = await read_upload(
        file, max_bytes=LESSON_FILE_BLOCK_MAX_BYTES,
    )
    oid = await interactor.run(
        AddFileBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            data=data,
            content_type=content_type,
            title=title,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/file",
    summary="Replace the file and/or title of a file block",
    operation_id="updateFileBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
        StorageQuotaExceededError: STORAGE_QUOTA_EXCEEDED_RULE,
    },
)
async def update_file_block(
    request: Request,
    interactor: FromDishka[UpdateFileBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
    file: UploadFile | None = File(  # noqa: B008
        default=None,
        description=(
            "New file bytes. Omit to update only the title."
        ),
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description="New caption, or omit to clear the existing one.",
    ),
) -> None:
    """Update the file-block: replace the file, the title, or both.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409 — block isn't of type `file`.
        StorageQuotaExceededError: HTTP 413 — new file would exceed plan cap.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    if file is not None:
        data, content_type = await read_upload(
            file, max_bytes=LESSON_FILE_BLOCK_MAX_BYTES,
        )
    else:
        data, content_type = None, None
    await interactor.run(
        UpdateFileBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            data=data,
            content_type=content_type,
            title=title,
        ),
    )


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/video-file",
    summary="Upload a video and append a video-file block to a lesson",
    operation_id="addVideoFileBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
        StorageQuotaExceededError: STORAGE_QUOTA_EXCEEDED_RULE,
    },
)
async def add_video_file_block(
    request: Request,
    interactor: FromDishka[AddVideoFileBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
    file: UploadFile = File(  # noqa: B008
        description=(
            "Video file bytes. Must have a `video/*` content type "
            "(HTTP 415 `WrongFileContentType` otherwise)."
        ),
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description=(
            "Optional caption. Max "
            f"{BLOCK_TITLE_MAX_LEN} chars (`BLOCK_TITLE_MAX_LEN`)."
        ),
    ),
) -> CreatedLessonBlockSchema:
    """Upload a video and append a video-file block. Author-only.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        StorageQuotaExceededError: HTTP 413.
        WrongFileContentTypeError: HTTP 415 — file is not a video.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    data, content_type = await read_upload(
        file, max_bytes=LESSON_VIDEO_BLOCK_MAX_BYTES,
    )
    oid = await interactor.run(
        AddVideoFileBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            data=data,
            content_type=content_type,
            title=title,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/video-file",
    summary="Replace the video and/or title of a video-file block",
    operation_id="updateVideoFileBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
        StorageQuotaExceededError: STORAGE_QUOTA_EXCEEDED_RULE,
    },
)
async def update_video_file_block(
    request: Request,
    interactor: FromDishka[UpdateVideoFileBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
    file: UploadFile | None = File(  # noqa: B008
        default=None,
        description="New video bytes. Omit to update only the title.",
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description="New caption, or omit to clear.",
    ),
) -> None:
    """Update video-file block: new video, new title, or both.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409.
        StorageQuotaExceededError: HTTP 413.
        WrongFileContentTypeError: HTTP 415.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    if file is not None:
        data, content_type = await read_upload(
            file, max_bytes=LESSON_VIDEO_BLOCK_MAX_BYTES,
        )
    else:
        data, content_type = None, None
    await interactor.run(
        UpdateVideoFileBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            data=data,
            content_type=content_type,
            title=title,
        ),
    )


def _zip_collage_uploads(
    files: list[UploadFile],
    captions: list[str] | None,
) -> list[tuple[UploadFile, str | None]]:
    """Pair multipart ``files[i]`` with ``captions[i]``.

    A missing ``captions`` array means "no captions at all"; a present
    array must match ``files`` in length — anything else is ambiguous
    and surfaces as ``InvalidCollageCaptionsLengthError`` at HTTP 422
    via the existing FieldError rule.
    """
    if captions is None:
        return [(f, None) for f in files]
    if len(captions) != len(files):
        raise ValueError(
            "collage `captions` length must equal `files` length",
        )
    # Empty string means "no caption" (clients can't omit individual
    # entries in a multipart list — they always send all positions).
    return [(f, c or None) for f, c in zip(files, captions, strict=True)]


async def _read_collage_items(
    files: list[UploadFile],
    captions: list[str] | None,
) -> tuple[CollageItemUpload, ...]:
    pairs = _zip_collage_uploads(files, captions)
    out: list[CollageItemUpload] = []
    for f, c in pairs:
        data, content_type = await read_upload(
            f, max_bytes=LESSON_COLLAGE_ITEM_MAX_BYTES,
        )
        out.append(
            CollageItemUpload(data=data, content_type=content_type, caption=c),
        )
    return tuple(out)


@router.post(
    "/{course_id}/lessons/{lesson_id}/blocks/photo-collage",
    summary="Upload photos and append a photo-collage block to a lesson",
    operation_id="addPhotoCollageBlock",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedLessonBlockSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
        StorageQuotaExceededError: STORAGE_QUOTA_EXCEEDED_RULE,
    },
)
async def add_photo_collage_block(
    request: Request,
    interactor: FromDishka[AddPhotoCollageBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    lesson_id: Annotated[UUID, _LESSON_ID_PATH],
    files: list[UploadFile] = File(  # noqa: B008
        description=(
            "Ordered list of photo bytes. Order in the multipart body "
            "becomes the persisted collage order. Each item must have "
            "an `image/*` content type. Min "
            f"`PHOTO_COLLAGE_MIN_ITEMS` ({PHOTO_COLLAGE_MIN_ITEMS}), "
            f"max `PHOTO_COLLAGE_MAX_ITEMS` ({PHOTO_COLLAGE_MAX_ITEMS})."
        ),
    ),
    captions: list[str] | None = Form(  # noqa: B008
        default=None,
        description=(
            "Optional per-photo captions. If present, length must match "
            "`files`. Empty string at a position means no caption for "
            "that photo. Max length per caption: "
            f"`PHOTO_COLLAGE_CAPTION_MAX_LEN` "
            f"({PHOTO_COLLAGE_CAPTION_MAX_LEN}) chars."
        ),
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description=(
            "Optional collage title. Max "
            f"{BLOCK_TITLE_MAX_LEN} chars (`BLOCK_TITLE_MAX_LEN`)."
        ),
    ),
) -> CreatedLessonBlockSchema:
    """Upload all photos and append a photo-collage block. Author-only.

    Every uploaded file must have an `image/*` content type.

    Returns:
        ``201 Created`` with the new block's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        StorageQuotaExceededError: HTTP 413.
        WrongFileContentTypeError: HTTP 415.
        FieldError: HTTP 422 — title / caption VO violation, item
            count violation, or file too large.
    """
    del course_id
    ctx = await auth.authenticate(request)
    items = await _read_collage_items(files, captions)
    oid = await interactor.run(
        AddPhotoCollageBlockCommand(
            actor_id=ctx.user_id,
            lesson_id=CourseLessonID(lesson_id),
            items=items,
            title=title,
        ),
    )
    return CreatedLessonBlockSchema(oid=oid)


@router.patch(
    "/{course_id}/blocks/{block_id}/photo-collage",
    summary="Replace the items and title of a photo-collage block",
    operation_id="updatePhotoCollageBlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        WrongBlockTypeError: WRONG_BLOCK_TYPE_RULE,
        WrongFileContentTypeError: WRONG_FILE_CONTENT_TYPE_RULE,
    },
)
async def update_photo_collage_block(
    request: Request,
    interactor: FromDishka[UpdatePhotoCollageBlockCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
    block_id: Annotated[UUID, _BLOCK_ID_PATH],
    files: list[UploadFile] = File(  # noqa: B008
        description=(
            "New ordered list of photo bytes — full replace; the new "
            "set is the complete new state."
        ),
    ),
    captions: list[str] | None = Form(  # noqa: B008
        default=None,
        description="New optional per-photo captions; same rules as add.",
    ),
    title: str | None = Form(  # noqa: B008
        default=None,
        max_length=BLOCK_TITLE_MAX_LEN,
        description="New title, or omit to clear.",
    ),
) -> None:
    """Replace items and title of a photo-collage block.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        WrongBlockTypeError: HTTP 409.
        WrongFileContentTypeError: HTTP 415.
        FieldError: HTTP 422.
    """
    del course_id
    ctx = await auth.authenticate(request)
    items = await _read_collage_items(files, captions)
    await interactor.run(
        UpdatePhotoCollageBlockCommand(
            actor_id=ctx.user_id,
            block_id=LessonBlockID(block_id),
            items=items,
            title=title,
        ),
    )


# ============================== draft reset ============================== #


class ResetCourseDraftSchema(BaseModel):
    """Body for ``POST /courses/{course_id}/draft/reset``.

    Identifies the release whose snapshot the draft should be
    rehydrated from. The release must belong to the same course;
    otherwise HTTP 404.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"},
            ],
        },
    )

    release_id: UUID = Field(
        description=(
            "UUID of the release whose snapshot will replace the "
            "current draft. Must belong to the same course."
        ),
        examples=["7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"],
    )


@router.post(
    "/{course_id}/draft/reset",
    summary="Reset draft to a previous release's snapshot",
    operation_id="resetCourseDraft",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {ProductDoesNotSupportError: PRODUCT_DOES_NOT_SUPPORT_RULE},
)
async def reset_draft(
    request: Request,
    payload: ResetCourseDraftSchema,
    interactor: FromDishka[ResetCourseDraftCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: Annotated[UUID, _COURSE_ID_PATH],
) -> None:
    """Discard the current draft and rehydrate it from a release snapshot.

    Author-only. The current draft (modules / lessons / blocks +
    child rows) is wiped via FK cascade and replaced with a fresh
    copy of ``release_id``'s snapshot. New UUIDs are generated for
    every restored row, so any local references in connected
    clients become stale — a ``DRAFT_RESET`` WS event is published
    after commit, instructing all open authors' tabs to refetch
    the tree.

    Existing releases are untouched; students stay pinned to their
    purchased version.

    Args:
        request: Source of the access cookie.
        payload: ``{"release_id": "<UUID>"}``.
        interactor: Injected handler.
        auth: Injected authenticator.
        course_id: Target course UUID.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403 — caller isn't the course author.
        EntityNotFoundError: HTTP 404 — course not found, release
            not found, or the release belongs to a different course.
        ProductDoesNotSupportError: HTTP 409 — product is not a course.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ResetCourseDraftCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(course_id),
            release_id=CourseReleaseID(payload.release_id),
        ),
    )
