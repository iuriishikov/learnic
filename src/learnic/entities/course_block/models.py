import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_block.constants import (
    CHOICE_BLOCK_MAX_OPTIONS,
    CHOICE_BLOCK_MIN_OPTIONS,
    CODE_BLOCK_MAX_TABS,
    TEXT_INPUT_MAX_ACCEPTED,
    TEXT_INPUT_MIN_ACCEPTED,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.errors import (
    CorrectOptionNotInOptionsError,
    CorrectOptionsNotSubsetError,
    DuplicateAcceptedAnswerError,
    DuplicateChoiceOptionIdError,
    DuplicateChoiceOptionLabelError,
    DuplicateCodeTabLabelError,
    EmptyCodeTabsError,
    EmptyCorrectOptionsError,
    TooFewAcceptedAnswersError,
    TooFewChoiceOptionsError,
    TooManyAcceptedAnswersError,
    TooManyChoiceOptionsError,
    TooManyCodeTabsError,
)
from learnic.entities.course_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.course_block.value_objects import (
    AcceptedAnswer,
    ChoiceOptionLabel,
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.product.ids import ProductID


@dataclass
class HtmlBlock(BaseEntity[LessonBlockID]):
    """A draft HTML-content block inside a lesson.

    ``product_id`` is denormalised from the parent lesson so
    ownership checks read the block alone (no extra JOIN).
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    html: HtmlContent
    position: int
    created_at: datetime
    updated_at: datetime

    @property
    def type(self) -> BlockType:
        return BlockType.HTML

    def update_html(self, new_html: HtmlContent) -> None:
        self.html = new_html

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        html: HtmlContent,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            html=html,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class KatexBlock(BaseEntity[LessonBlockID]):
    """A draft KaTeX-source block inside a lesson.

    Body is KaTeX-flavored math source — a strict subset of LaTeX
    rendered client-side via the KaTeX library. See
    https://katex.org/docs/support_table.html for the supported
    command surface.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    source: KatexSource
    position: int
    created_at: datetime
    updated_at: datetime

    @property
    def type(self) -> BlockType:
        return BlockType.KATEX

    def update_source(self, new_source: KatexSource) -> None:
        self.source = new_source

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        source: KatexSource,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            source=source,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class RutubeVideoBlock(BaseEntity[LessonBlockID]):
    """A draft Rutube-embed block inside a lesson.

    Rutube is the only video provider supported today; if/when
    another provider is needed (YouTube, Vimeo) it will get its
    own block type rather than a generic ``video`` one — embed
    URL templates and id formats diverge enough that a single
    abstraction would lie.

    The embed URL is computed at the presentation layer from
    ``external_id`` as ``https://rutube.ru/play/embed/{id}/``.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    external_id: RutubeVideoID
    position: int
    created_at: datetime
    updated_at: datetime
    title: VideoTitle | None = None

    @property
    def type(self) -> BlockType:
        return BlockType.RUTUBE_VIDEO

    def update_external_id(self, new_id: RutubeVideoID) -> None:
        self.external_id = new_id

    def update_title(self, new_title: VideoTitle | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        external_id: RutubeVideoID,
        position: int,
        title: VideoTitle | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            external_id=external_id,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


@dataclass(frozen=True, slots=True)
class CodeTab:
    """One tab inside a :class:`CodeBlock`.

    A tab is a ``(label, source, language)`` triple. ``label`` is
    visible to the student in the tab strip — empty string is only
    allowed for single-tab blocks (where no strip is rendered).
    Multi-tab blocks must have non-empty unique labels; that
    invariant lives on the parent :class:`CodeBlock` so it can see
    all tabs at once.
    """

    label: CodeTabLabel
    source: CodeSource
    language: CodeLanguage


def _validate_tabs(tabs: list[CodeTab]) -> None:
    """Apply the cross-tab invariants: count + label uniqueness."""
    if not tabs:
        raise EmptyCodeTabsError()
    if len(tabs) > CODE_BLOCK_MAX_TABS:
        raise TooManyCodeTabsError(CODE_BLOCK_MAX_TABS)
    if len(tabs) > 1:
        seen: set[str] = set()
        for tab in tabs:
            if not tab.label.value:
                # Multi-tab blocks need real labels — empty label is
                # only meaningful for the single-tab case.
                raise DuplicateCodeTabLabelError("")
            if tab.label.value in seen:
                raise DuplicateCodeTabLabelError(tab.label.value)
            seen.add(tab.label.value)


@dataclass
class CodeBlock(BaseEntity[LessonBlockID]):
    """A draft source-code block inside a lesson.

    A code block is a non-empty list of tabs (variants). The most
    common case is a single tab — the tab strip is hidden client-
    side, so the block reads as a plain code snippet. Multi-tab
    blocks are for variant snippets like ``npm`` / ``pnpm`` /
    ``yarn``: same intent, different shells.

    ``language`` per tab is bound to :class:`CodeBlockLanguage`;
    sources are preserved verbatim.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    tabs: list[CodeTab]
    position: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_tabs(self.tabs)

    @property
    def type(self) -> BlockType:
        return BlockType.CODE

    def replace_tabs(self, new_tabs: list[CodeTab]) -> None:
        _validate_tabs(new_tabs)
        self.tabs = new_tabs

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        tabs: list[CodeTab],
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            tabs=tabs,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class ChoiceOption:
    """One selectable option inside a choice block.

    A pair of ``(oid, label)``. ``oid`` is a stable domain-generated
    UUID so the "correct" pointer survives reorder/label edits;
    ``label`` is the visible text shown to the student.
    Cross-option uniqueness (labels, ids, "correct ∈ options")
    lives on the parent block, see :class:`SingleChoiceBlock` /
    :class:`MultiChoiceBlock`.
    """

    oid: ChoiceOptionID
    label: ChoiceOptionLabel

    @classmethod
    def create(cls, label: ChoiceOptionLabel) -> Self:
        """Mint a new option with a freshly generated id."""
        return cls(oid=ChoiceOptionID(uuid.uuid4()), label=label)


def _validate_options(options: list[ChoiceOption]) -> None:
    """Apply the cross-option invariants: count + label / id uniqueness."""
    if len(options) < CHOICE_BLOCK_MIN_OPTIONS:
        raise TooFewChoiceOptionsError(CHOICE_BLOCK_MIN_OPTIONS)
    if len(options) > CHOICE_BLOCK_MAX_OPTIONS:
        raise TooManyChoiceOptionsError(CHOICE_BLOCK_MAX_OPTIONS)
    seen_ids: set[ChoiceOptionID] = set()
    seen_labels: set[str] = set()
    for opt in options:
        if opt.oid in seen_ids:
            raise DuplicateChoiceOptionIdError(str(opt.oid))
        seen_ids.add(opt.oid)
        if opt.label.value in seen_labels:
            raise DuplicateChoiceOptionLabelError(opt.label.value)
        seen_labels.add(opt.label.value)


@dataclass
class SingleChoiceBlock(BaseEntity[LessonBlockID]):
    """A draft single-choice answer block.

    Stores the option list and the one ``correct_option_id``.
    The question prompt itself is NOT part of this block — it
    lives in a preceding HTML block. The student picks exactly
    one option; the server validates against ``correct_option_id``
    and never leaks it through the public read-side view.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    options: list[ChoiceOption]
    correct_option_id: ChoiceOptionID
    position: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_options(self.options)
        if self.correct_option_id not in {o.oid for o in self.options}:
            raise CorrectOptionNotInOptionsError(str(self.correct_option_id))

    @property
    def type(self) -> BlockType:
        return BlockType.SINGLE_CHOICE

    def check(self, answer: ChoiceOptionID) -> bool:
        """Return whether the student's pick matches the correct option."""
        return answer == self.correct_option_id

    def replace_options(
        self,
        new_options: list[ChoiceOption],
        new_correct_option_id: ChoiceOptionID,
    ) -> None:
        # Apply both invariants together — if the new correct id
        # doesn't appear in the new options the call fails atomically.
        _validate_options(new_options)
        if new_correct_option_id not in {o.oid for o in new_options}:
            raise CorrectOptionNotInOptionsError(str(new_correct_option_id))
        self.options = new_options
        self.correct_option_id = new_correct_option_id

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        options: list[ChoiceOption],
        correct_option_id: ChoiceOptionID,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            options=options,
            correct_option_id=correct_option_id,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class MultiChoiceBlock(BaseEntity[LessonBlockID]):
    """A draft multi-choice answer block.

    Like :class:`SingleChoiceBlock` but with a non-empty set of
    correct option ids — the student picks zero or more and the
    answer is correct iff the picked set equals
    ``correct_option_ids`` exactly. Order does not matter.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    options: list[ChoiceOption]
    correct_option_ids: frozenset[ChoiceOptionID]
    position: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_options(self.options)
        if not self.correct_option_ids:
            raise EmptyCorrectOptionsError()
        option_ids = {o.oid for o in self.options}
        unknown = self.correct_option_ids - option_ids
        if unknown:
            raise CorrectOptionsNotSubsetError(
                tuple(sorted(str(o) for o in unknown)),
            )

    @property
    def type(self) -> BlockType:
        return BlockType.MULTI_CHOICE

    def check(self, answer: frozenset[ChoiceOptionID]) -> bool:
        """Return whether the picked set equals the correct set exactly."""
        return answer == self.correct_option_ids

    def replace_options(
        self,
        new_options: list[ChoiceOption],
        new_correct_option_ids: frozenset[ChoiceOptionID],
    ) -> None:
        _validate_options(new_options)
        if not new_correct_option_ids:
            raise EmptyCorrectOptionsError()
        option_ids = {o.oid for o in new_options}
        unknown = new_correct_option_ids - option_ids
        if unknown:
            raise CorrectOptionsNotSubsetError(
                tuple(sorted(str(o) for o in unknown)),
            )
        self.options = new_options
        self.correct_option_ids = new_correct_option_ids

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        options: list[ChoiceOption],
        correct_option_ids: frozenset[ChoiceOptionID],
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            options=options,
            correct_option_ids=correct_option_ids,
            position=position,
            created_at=now,
            updated_at=now,
        )


def _normalise_text_answer(
    value: str,
    *,
    case_sensitive: bool,
    trim_whitespace: bool,
) -> str:
    out = value.strip() if trim_whitespace else value
    return out if case_sensitive else out.casefold()


def _validate_accepted_answers(
    accepted_answers: list[AcceptedAnswer],
    *,
    case_sensitive: bool,
    trim_whitespace: bool,
) -> None:
    if len(accepted_answers) < TEXT_INPUT_MIN_ACCEPTED:
        raise TooFewAcceptedAnswersError(TEXT_INPUT_MIN_ACCEPTED)
    if len(accepted_answers) > TEXT_INPUT_MAX_ACCEPTED:
        raise TooManyAcceptedAnswersError(TEXT_INPUT_MAX_ACCEPTED)
    seen: set[str] = set()
    for a in accepted_answers:
        # Uniqueness is checked under the block's own normalisation —
        # otherwise toggling ``trim_whitespace`` on later would silently
        # introduce collisions the author can't see.
        norm = _normalise_text_answer(
            a.value,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
        )
        if norm in seen:
            raise DuplicateAcceptedAnswerError(a.value)
        seen.add(norm)


@dataclass
class TextInputBlock(BaseEntity[LessonBlockID]):
    """A draft free-text answer block.

    The student types into a single-line input; the server compares
    the submission against ``accepted_answers`` under the block's
    own normalisation flags. There is no fuzzy match, no regex —
    answers are short, exact-match-after-normalisation strings.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    accepted_answers: list[AcceptedAnswer]
    case_sensitive: bool
    trim_whitespace: bool
    position: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_accepted_answers(
            self.accepted_answers,
            case_sensitive=self.case_sensitive,
            trim_whitespace=self.trim_whitespace,
        )

    @property
    def type(self) -> BlockType:
        return BlockType.TEXT_INPUT

    def check(self, answer: str) -> bool:
        """Return whether ``answer`` matches any accepted value."""
        target = _normalise_text_answer(
            answer,
            case_sensitive=self.case_sensitive,
            trim_whitespace=self.trim_whitespace,
        )
        return any(
            target
            == _normalise_text_answer(
                a.value,
                case_sensitive=self.case_sensitive,
                trim_whitespace=self.trim_whitespace,
            )
            for a in self.accepted_answers
        )

    def replace_answers(
        self,
        new_accepted_answers: list[AcceptedAnswer],
        case_sensitive: bool,
        trim_whitespace: bool,
    ) -> None:
        _validate_accepted_answers(
            new_accepted_answers,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
        )
        self.accepted_answers = new_accepted_answers
        self.case_sensitive = case_sensitive
        self.trim_whitespace = trim_whitespace

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        accepted_answers: list[AcceptedAnswer],
        case_sensitive: bool,
        trim_whitespace: bool,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            accepted_answers=accepted_answers,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
            position=position,
            created_at=now,
            updated_at=now,
        )


LessonBlock = (
    HtmlBlock
    | KatexBlock
    | RutubeVideoBlock
    | CodeBlock
    | SingleChoiceBlock
    | MultiChoiceBlock
    | TextInputBlock
)
