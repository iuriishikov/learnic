"""Typed payloads for the course-content WebSocket channel.

Each kind of :class:`ContentEvent` carries its own payload
dataclass; the discriminator is the class-level :attr:`KIND`
constant. The union :data:`ContentPayload` is closed — adding a
new kind means adding a dataclass and extending the union and
:func:`payload_from_wire`. mypy then flags every consumer that
does not handle the new variant.

Wire shape: ``dataclasses.asdict(payload)`` produces the payload
sub-object the SPA expects (the discriminator lives in the outer
envelope, not in the inner payload). The bus serializer adds the
envelope (``kind`` from ``type(payload).KIND``, ``product_id``,
``actor_id``, ``occurred_at``).

For each payload that captures a snapshot of a domain entity, a
``from_<entity>(...)`` classmethod centralises the projection so
command handlers stay free of presentation-level wire shaping.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, assert_never

from learnic.entities.course_block.models import (
    CodeBlock,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    MultiChoiceBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.models import CourseModule
from learnic.entities.course_release.models import CourseRelease

# Mirror of `presentation/http/routes/course_content._rutube_embed_url`.
# Kept in `application/` so handlers can build the snapshot without
# crossing into `presentation/`. If Rutube ever changes the path,
# both call sites must be updated together.
_RUTUBE_EMBED_URL_TEMPLATE = "https://rutube.ru/play/embed/{external_id}/"


# ---------------------------------------------------------------- #
# Block snapshots (used inside lesson / block payloads).
# Discriminated by the `type` field, same shape the REST draft
# endpoint (`LessonBlockSchema`) returns so SPAs can splice them
# into the cache without a refetch.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class HtmlBlockSnapshot:
    type: Literal["html"]
    oid: str
    position: int
    html: str


@dataclass(slots=True, frozen=True)
class KatexBlockSnapshot:
    type: Literal["katex"]
    oid: str
    position: int
    source: str


@dataclass(slots=True, frozen=True)
class CodeBlockTabSnapshot:
    label: str
    source: str
    language: str


@dataclass(slots=True, frozen=True)
class CodeBlockSnapshot:
    type: Literal["code"]
    oid: str
    position: int
    tabs: list[CodeBlockTabSnapshot]


@dataclass(slots=True, frozen=True)
class RutubeVideoBlockSnapshot:
    type: Literal["rutube_video"]
    oid: str
    position: int
    external_id: str
    embed_url: str
    title: str | None


@dataclass(slots=True, frozen=True)
class ChoiceOptionSnapshot:
    oid: str
    label: str


@dataclass(slots=True, frozen=True)
class SingleChoiceBlockSnapshot:
    """Authoring-side wire shape.

    The ``correct_option_id`` is sent verbatim because this channel
    is auth-gated for course collaborators (authors). The
    student-facing public view, exposed only through the release
    HTTP endpoint, strips the correct id at the presentation layer.
    """

    type: Literal["single_choice"]
    oid: str
    position: int
    options: list[ChoiceOptionSnapshot]
    correct_option_id: str


@dataclass(slots=True, frozen=True)
class MultiChoiceBlockSnapshot:
    type: Literal["multi_choice"]
    oid: str
    position: int
    options: list[ChoiceOptionSnapshot]
    correct_option_ids: list[str]


@dataclass(slots=True, frozen=True)
class TextInputBlockSnapshot:
    type: Literal["text_input"]
    oid: str
    position: int
    accepted_answers: list[str]
    case_sensitive: bool
    trim_whitespace: bool


BlockSnapshot = (
    HtmlBlockSnapshot
    | KatexBlockSnapshot
    | CodeBlockSnapshot
    | RutubeVideoBlockSnapshot
    | SingleChoiceBlockSnapshot
    | MultiChoiceBlockSnapshot
    | TextInputBlockSnapshot
)


def _block_snapshot(block: LessonBlock) -> BlockSnapshot:
    if isinstance(block, HtmlBlock):
        return HtmlBlockSnapshot(
            type="html",
            oid=str(block.oid),
            position=block.position,
            html=block.html.value,
        )
    if isinstance(block, KatexBlock):
        return KatexBlockSnapshot(
            type="katex",
            oid=str(block.oid),
            position=block.position,
            source=block.source.value,
        )
    if isinstance(block, RutubeVideoBlock):
        external_id = block.external_id.value
        return RutubeVideoBlockSnapshot(
            type="rutube_video",
            oid=str(block.oid),
            position=block.position,
            external_id=external_id,
            embed_url=_RUTUBE_EMBED_URL_TEMPLATE.format(
                external_id=external_id,
            ),
            title=block.title.value if block.title is not None else None,
        )
    if isinstance(block, CodeBlock):
        return CodeBlockSnapshot(
            type="code",
            oid=str(block.oid),
            position=block.position,
            tabs=[
                CodeBlockTabSnapshot(
                    label=tab.label.value,
                    source=tab.source.value,
                    language=tab.language.value,
                )
                for tab in block.tabs
            ],
        )
    if isinstance(block, SingleChoiceBlock):
        return SingleChoiceBlockSnapshot(
            type="single_choice",
            oid=str(block.oid),
            position=block.position,
            options=[
                ChoiceOptionSnapshot(oid=str(o.oid), label=o.label.value)
                for o in block.options
            ],
            correct_option_id=str(block.correct_option_id),
        )
    if isinstance(block, MultiChoiceBlock):
        return MultiChoiceBlockSnapshot(
            type="multi_choice",
            oid=str(block.oid),
            position=block.position,
            options=[
                ChoiceOptionSnapshot(oid=str(o.oid), label=o.label.value)
                for o in block.options
            ],
            correct_option_ids=[str(o) for o in block.correct_option_ids],
        )
    if isinstance(block, TextInputBlock):
        return TextInputBlockSnapshot(
            type="text_input",
            oid=str(block.oid),
            position=block.position,
            accepted_answers=[a.value for a in block.accepted_answers],
            case_sensitive=block.case_sensitive,
            trim_whitespace=block.trim_whitespace,
        )
    assert_never(block)


# ---------------------------------------------------------------- #
# Module / lesson snapshots.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class LessonSnapshot:
    oid: str
    title: str
    position: int
    blocks: list[BlockSnapshot]


@dataclass(slots=True, frozen=True)
class ModuleSnapshot:
    oid: str
    title: str
    description: str | None
    position: int
    lessons: list[LessonSnapshot]


# ---------------------------------------------------------------- #
# Content payloads — one per kind. The class-level ``KIND``
# constant is the envelope discriminator; ``dataclasses.asdict``
# does not include ``ClassVar`` fields, so it emits only the
# payload-specific data — exactly the wire shape the SPA expects.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class ModuleAddedPayload:
    KIND: ClassVar[Literal["module_added"]] = "module_added"
    module: ModuleSnapshot

    @classmethod
    def from_entity(cls, module: CourseModule) -> "ModuleAddedPayload":
        return cls(
            module=ModuleSnapshot(
                oid=str(module.oid),
                title=module.title.value,
                description=(
                    module.description.value if module.description is not None else None
                ),
                position=module.position,
                lessons=[],
            ),
        )


@dataclass(slots=True, frozen=True)
class ModuleRenamedPayload:
    KIND: ClassVar[Literal["module_renamed"]] = "module_renamed"
    module_id: str
    title: str


@dataclass(slots=True, frozen=True)
class ModuleDescriptionUpdatedPayload:
    KIND: ClassVar[Literal["module_description_updated"]] = "module_description_updated"
    module_id: str
    description: str | None


@dataclass(slots=True, frozen=True)
class ModulesReorderedPayload:
    KIND: ClassVar[Literal["modules_reordered"]] = "modules_reordered"
    ordered_ids: list[str]


@dataclass(slots=True, frozen=True)
class ModuleDeletedPayload:
    KIND: ClassVar[Literal["module_deleted"]] = "module_deleted"
    module_id: str


@dataclass(slots=True, frozen=True)
class LessonAddedPayload:
    KIND: ClassVar[Literal["lesson_added"]] = "lesson_added"
    module_id: str
    lesson: LessonSnapshot

    @classmethod
    def from_entity(
        cls,
        *,
        module_id: CourseModuleID,
        lesson: CourseLesson,
    ) -> "LessonAddedPayload":
        return cls(
            module_id=str(module_id),
            lesson=LessonSnapshot(
                oid=str(lesson.oid),
                title=lesson.title.value,
                position=lesson.position,
                blocks=[],
            ),
        )


@dataclass(slots=True, frozen=True)
class LessonRenamedPayload:
    KIND: ClassVar[Literal["lesson_renamed"]] = "lesson_renamed"
    lesson_id: str
    title: str


@dataclass(slots=True, frozen=True)
class LessonMovedPayload:
    KIND: ClassVar[Literal["lesson_moved"]] = "lesson_moved"
    lesson_id: str
    from_module_id: str
    to_module_id: str
    position: int

    @classmethod
    def of(
        cls,
        *,
        lesson_id: CourseLessonID,
        from_module_id: CourseModuleID,
        to_module_id: CourseModuleID,
        position: int,
    ) -> "LessonMovedPayload":
        return cls(
            lesson_id=str(lesson_id),
            from_module_id=str(from_module_id),
            to_module_id=str(to_module_id),
            position=position,
        )


@dataclass(slots=True, frozen=True)
class LessonsReorderedPayload:
    KIND: ClassVar[Literal["lessons_reordered"]] = "lessons_reordered"
    module_id: str
    ordered_ids: list[str]


@dataclass(slots=True, frozen=True)
class LessonDeletedPayload:
    KIND: ClassVar[Literal["lesson_deleted"]] = "lesson_deleted"
    lesson_id: str


@dataclass(slots=True, frozen=True)
class BlockAddedPayload:
    KIND: ClassVar[Literal["block_added"]] = "block_added"
    lesson_id: str
    block: BlockSnapshot

    @classmethod
    def from_entity(
        cls,
        *,
        lesson_id: CourseLessonID,
        block: LessonBlock,
    ) -> "BlockAddedPayload":
        return cls(
            lesson_id=str(lesson_id),
            block=_block_snapshot(block),
        )


@dataclass(slots=True, frozen=True)
class BlockUpdatedPayload:
    KIND: ClassVar[Literal["block_updated"]] = "block_updated"
    block: BlockSnapshot

    @classmethod
    def from_entity(cls, block: LessonBlock) -> "BlockUpdatedPayload":
        return cls(block=_block_snapshot(block))


@dataclass(slots=True, frozen=True)
class BlockDeletedPayload:
    KIND: ClassVar[Literal["block_deleted"]] = "block_deleted"
    block_id: str


@dataclass(slots=True, frozen=True)
class BlocksReorderedPayload:
    KIND: ClassVar[Literal["blocks_reordered"]] = "blocks_reordered"
    lesson_id: str
    ordered_ids: list[str]


@dataclass(slots=True, frozen=True)
class ReleaseCreatedPayload:
    """Payload for ``release_created``.

    The inner ``kind`` field is the release kind enum value
    (``major`` / ``minor`` / ``patch``) — distinct from the
    envelope-level event ``kind`` discriminator (always
    ``release_created`` here, held in :attr:`KIND`).
    """

    KIND: ClassVar[Literal["release_created"]] = "release_created"
    release_id: str
    ordinal: int
    version: list[int]
    kind: str

    @classmethod
    def from_entity(cls, release: CourseRelease) -> "ReleaseCreatedPayload":
        return cls(
            release_id=str(release.oid),
            ordinal=release.ordinal,
            version=[
                release.version.major,
                release.version.minor,
                release.version.patch,
            ],
            kind=release.kind.value,
        )


@dataclass(slots=True, frozen=True)
class DraftResetPayload:
    KIND: ClassVar[Literal["draft_reset"]] = "draft_reset"
    release_id: str
    ordinal: int
    version: list[int]

    @classmethod
    def from_entity(cls, release: CourseRelease) -> "DraftResetPayload":
        return cls(
            release_id=str(release.oid),
            ordinal=release.ordinal,
            version=[
                release.version.major,
                release.version.minor,
                release.version.patch,
            ],
        )


ContentPayload = (
    ModuleAddedPayload
    | ModuleRenamedPayload
    | ModuleDescriptionUpdatedPayload
    | ModulesReorderedPayload
    | ModuleDeletedPayload
    | LessonAddedPayload
    | LessonRenamedPayload
    | LessonMovedPayload
    | LessonsReorderedPayload
    | LessonDeletedPayload
    | BlockAddedPayload
    | BlockUpdatedPayload
    | BlockDeletedPayload
    | BlocksReorderedPayload
    | ReleaseCreatedPayload
    | DraftResetPayload
)


def payload_from_wire(kind: str, data: dict[str, Any]) -> ContentPayload:
    """Reconstruct a typed payload from its on-wire dict shape.

    The inverse of ``dataclasses.asdict(payload)`` — used by the
    Redis subscriber to rebuild typed events as they arrive. The
    ``kind`` comes from the envelope; ``data`` is the inner
    payload sub-object.

    Adding a new payload requires adding a branch here. The
    trailing ``raise`` guards against silently dropping an
    unknown kind sent by an out-of-date publisher.
    """
    if kind == ModuleAddedPayload.KIND:
        return ModuleAddedPayload(module=_module_snapshot_from_wire(data["module"]))
    if kind == ModuleRenamedPayload.KIND:
        return ModuleRenamedPayload(
            module_id=data["module_id"],
            title=data["title"],
        )
    if kind == ModuleDescriptionUpdatedPayload.KIND:
        return ModuleDescriptionUpdatedPayload(
            module_id=data["module_id"],
            description=data["description"],
        )
    if kind == ModulesReorderedPayload.KIND:
        return ModulesReorderedPayload(ordered_ids=list(data["ordered_ids"]))
    if kind == ModuleDeletedPayload.KIND:
        return ModuleDeletedPayload(module_id=data["module_id"])
    if kind == LessonAddedPayload.KIND:
        return LessonAddedPayload(
            module_id=data["module_id"],
            lesson=_lesson_snapshot_from_wire(data["lesson"]),
        )
    if kind == LessonRenamedPayload.KIND:
        return LessonRenamedPayload(
            lesson_id=data["lesson_id"],
            title=data["title"],
        )
    if kind == LessonMovedPayload.KIND:
        return LessonMovedPayload(
            lesson_id=data["lesson_id"],
            from_module_id=data["from_module_id"],
            to_module_id=data["to_module_id"],
            position=data["position"],
        )
    if kind == LessonsReorderedPayload.KIND:
        return LessonsReorderedPayload(
            module_id=data["module_id"],
            ordered_ids=list(data["ordered_ids"]),
        )
    if kind == LessonDeletedPayload.KIND:
        return LessonDeletedPayload(lesson_id=data["lesson_id"])
    if kind == BlockAddedPayload.KIND:
        return BlockAddedPayload(
            lesson_id=data["lesson_id"],
            block=_block_snapshot_from_wire(data["block"]),
        )
    if kind == BlockUpdatedPayload.KIND:
        return BlockUpdatedPayload(
            block=_block_snapshot_from_wire(data["block"]),
        )
    if kind == BlockDeletedPayload.KIND:
        return BlockDeletedPayload(block_id=data["block_id"])
    if kind == BlocksReorderedPayload.KIND:
        return BlocksReorderedPayload(
            lesson_id=data["lesson_id"],
            ordered_ids=list(data["ordered_ids"]),
        )
    if kind == ReleaseCreatedPayload.KIND:
        return ReleaseCreatedPayload(
            release_id=data["release_id"],
            ordinal=data["ordinal"],
            version=list(data["version"]),
            kind=data["kind"],
        )
    if kind == DraftResetPayload.KIND:
        return DraftResetPayload(
            release_id=data["release_id"],
            ordinal=data["ordinal"],
            version=list(data["version"]),
        )
    msg = f"unknown content payload kind: {kind!r}"
    raise ValueError(msg)


def _block_snapshot_from_wire(data: dict[str, Any]) -> BlockSnapshot:
    block_type = data["type"]
    if block_type == "html":
        return HtmlBlockSnapshot(
            type="html",
            oid=data["oid"],
            position=data["position"],
            html=data["html"],
        )
    if block_type == "katex":
        return KatexBlockSnapshot(
            type="katex",
            oid=data["oid"],
            position=data["position"],
            source=data["source"],
        )
    if block_type == "rutube_video":
        return RutubeVideoBlockSnapshot(
            type="rutube_video",
            oid=data["oid"],
            position=data["position"],
            external_id=data["external_id"],
            embed_url=data["embed_url"],
            title=data["title"],
        )
    if block_type == "code":
        return CodeBlockSnapshot(
            type="code",
            oid=data["oid"],
            position=data["position"],
            tabs=[
                CodeBlockTabSnapshot(
                    label=tab["label"],
                    source=tab["source"],
                    language=tab["language"],
                )
                for tab in data["tabs"]
            ],
        )
    if block_type == "single_choice":
        return SingleChoiceBlockSnapshot(
            type="single_choice",
            oid=data["oid"],
            position=data["position"],
            options=[
                ChoiceOptionSnapshot(oid=o["oid"], label=o["label"])
                for o in data["options"]
            ],
            correct_option_id=data["correct_option_id"],
        )
    if block_type == "multi_choice":
        return MultiChoiceBlockSnapshot(
            type="multi_choice",
            oid=data["oid"],
            position=data["position"],
            options=[
                ChoiceOptionSnapshot(oid=o["oid"], label=o["label"])
                for o in data["options"]
            ],
            correct_option_ids=list(data["correct_option_ids"]),
        )
    if block_type == "text_input":
        return TextInputBlockSnapshot(
            type="text_input",
            oid=data["oid"],
            position=data["position"],
            accepted_answers=list(data["accepted_answers"]),
            case_sensitive=data["case_sensitive"],
            trim_whitespace=data["trim_whitespace"],
        )
    msg = f"unknown block snapshot type: {block_type!r}"
    raise ValueError(msg)


def _lesson_snapshot_from_wire(data: dict[str, Any]) -> LessonSnapshot:
    return LessonSnapshot(
        oid=data["oid"],
        title=data["title"],
        position=data["position"],
        blocks=[_block_snapshot_from_wire(b) for b in data["blocks"]],
    )


def _module_snapshot_from_wire(data: dict[str, Any]) -> ModuleSnapshot:
    return ModuleSnapshot(
        oid=data["oid"],
        title=data["title"],
        description=data["description"],
        position=data["position"],
        lessons=[_lesson_snapshot_from_wire(lsn) for lsn in data["lessons"]],
    )
