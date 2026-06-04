import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.note_block.constants import (
    CHOICE_BLOCK_MAX_OPTIONS,
    CHOICE_BLOCK_MIN_OPTIONS,
    CODE_BLOCK_MAX_TABS,
    PHOTO_COLLAGE_MAX_ITEMS,
    PHOTO_COLLAGE_MIN_ITEMS,
    TEXT_INPUT_MAX_ACCEPTED,
    TEXT_INPUT_MIN_ACCEPTED,
)
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.errors import (
    CollageItemsMismatchError,
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
    TooFewCollageItemsError,
    TooManyCollageItemsError,
)
from learnic.entities.note_block.ids import (
    ChoiceOptionID,
    CollageItemID,
    LessonBlockID,
)
from learnic.entities.note_block.value_objects import (
    AcceptedAnswer,
    BlockTitle,
    ChoiceOptionLabel,
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    CollageCaption,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID


@dataclass
class HtmlBlock(BaseEntity[LessonBlockID]):
    """A draft HTML-content block inside a lesson.

    ``product_id`` is denormalised from the parent lesson so
    ownership checks read the block alone (no extra JOIN).
    """

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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
    """Apply the cross-option invariants: count + label / id uniqueness.

    Empty / blank labels are not deduplicated — a freshly created
    block legitimately ships with multiple empty placeholder rows
    the author fills in afterwards. Uniqueness still applies to
    every label the author has actually typed something into.
    """
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
        if not opt.label.value.strip():
            continue
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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
        # introduce collisions the author can't see. Empty / blank
        # placeholders are skipped — a freshly created block ships
        # with one (or more) empty rows the author hasn't filled in.
        norm = _normalise_text_answer(
            a.value,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
        )
        if not norm:
            continue
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

    lesson_id: NoteLessonID
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
        lesson_id: NoteLessonID,
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


@dataclass
class FileBlock(BaseEntity[LessonBlockID]):
    """A draft generic-file block inside a lesson.

    Carries a single ``file_id`` pointing at the ``files`` table —
    actual bytes live in S3. ``file_id`` is nullable on the entity
    (mirroring the ``ON DELETE SET NULL`` FK at the persistence
    boundary): if the backing file is purged later, the block
    survives as a "file missing" placeholder rather than vanishing
    with the file. No content-type whitelist at the domain layer —
    enforcement of "this is an arbitrary file" vs ``video/*`` vs
    ``image/*`` lives in the command handler that constructs the
    block (the handler reads the file's stored ``content_type``).
    """

    lesson_id: NoteLessonID
    product_id: ProductID
    file_id: FileID | None
    position: int
    created_at: datetime
    updated_at: datetime
    title: BlockTitle | None = None

    @property
    def type(self) -> BlockType:
        return BlockType.FILE

    def update_file(self, new_file_id: FileID) -> None:
        self.file_id = new_file_id

    def update_title(self, new_title: BlockTitle | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: NoteLessonID,
        product_id: ProductID,
        file_id: FileID,
        position: int,
        title: BlockTitle | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            file_id=file_id,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


@dataclass
class VideoFileBlock(BaseEntity[LessonBlockID]):
    """A draft uploaded-video block inside a lesson.

    Sibling of :class:`RutubeVideoBlock` — same playback affordance,
    different provider contract. Rutube blocks embed by external id;
    this block plays the bytes uploaded into the project's own
    storage. The two are deliberately separate types: their playback
    URLs, controls, and analytics flows diverge enough that a
    unified ``video`` type would be a fake abstraction.

    The "this file is actually a video" check (content-type prefix
    ``video/``) is enforced by the command handler at construction
    time, not at the VO/entity layer — the same ``file_id`` machinery
    is reused across all file-backed blocks.
    """

    lesson_id: NoteLessonID
    product_id: ProductID
    file_id: FileID | None
    position: int
    created_at: datetime
    updated_at: datetime
    title: BlockTitle | None = None

    @property
    def type(self) -> BlockType:
        return BlockType.VIDEO_FILE

    def update_file(self, new_file_id: FileID) -> None:
        self.file_id = new_file_id

    def update_title(self, new_title: BlockTitle | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: NoteLessonID,
        product_id: ProductID,
        file_id: FileID,
        position: int,
        title: BlockTitle | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            file_id=file_id,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


@dataclass(frozen=True, slots=True)
class CollageItem:
    """One photo inside a :class:`PhotoCollageBlock`.

    ``oid`` is a stable domain-generated UUID — the item lives in its
    own ``photo_collage_items`` row on the draft side, so granular
    edits (add / remove / reorder / caption) can address it by id
    instead of by position. ``file_id`` is nullable to survive
    backing-file deletion (same rationale as the parent block).
    ``caption`` is optional — a short hand-written note shown under
    the photo; anything longer belongs in an adjacent HTML block.
    """

    oid: CollageItemID
    file_id: FileID | None
    caption: CollageCaption | None = None


def _validate_collage_items(items: list[CollageItem]) -> None:
    """Apply collage-level invariants: bounded count."""
    if len(items) < PHOTO_COLLAGE_MIN_ITEMS:
        raise TooFewCollageItemsError(PHOTO_COLLAGE_MIN_ITEMS)
    if len(items) > PHOTO_COLLAGE_MAX_ITEMS:
        raise TooManyCollageItemsError(PHOTO_COLLAGE_MAX_ITEMS)


@dataclass
class PhotoCollageBlock(BaseEntity[LessonBlockID]):
    """A draft photo-collage block inside a lesson.

    A non-empty ordered list of :class:`CollageItem` (id + file +
    optional caption). Items are persisted as separate rows in the
    ``photo_collage_items`` child table on the draft side, so
    granular edits (add / remove / reorder / caption) address one
    photo by its stable ``oid``. The "each item is an image"
    invariant (content-type prefix ``image/``) is enforced by the
    command handler at construction time. Release snapshots
    continue to store items denormalised inside a JSONB column;
    the snapshotter assembles that JSONB from the new draft
    rows at snapshot time.
    """

    lesson_id: NoteLessonID
    product_id: ProductID
    items: list[CollageItem]
    position: int
    created_at: datetime
    updated_at: datetime
    title: BlockTitle | None = None

    def __post_init__(self) -> None:
        _validate_collage_items(self.items)

    @property
    def type(self) -> BlockType:
        return BlockType.PHOTO_COLLAGE

    def add_item(
        self,
        file_id: FileID,
        caption: CollageCaption | None = None,
    ) -> CollageItem:
        """Append a new item with a freshly-minted :class:`CollageItemID`.

        Raises :class:`TooManyCollageItemsError` if the addition would
        push the count over ``PHOTO_COLLAGE_MAX_ITEMS``. Returns the
        newly-created item so the caller can surface its oid back to
        the API client.
        """
        candidate = list(self.items)
        item = CollageItem(
            oid=CollageItemID(uuid.uuid4()),
            file_id=file_id,
            caption=caption,
        )
        candidate.append(item)
        _validate_collage_items(candidate)
        self.items = candidate
        return item

    def remove_item(self, item_id: CollageItemID) -> FileID | None:
        """Drop the item with the given ``oid``.

        Returns the file id freed by the removal (or ``None`` if the
        item had no backing file — placeholder rows survive backing-
        file deletion). Raises :class:`TooFewCollageItemsError` if
        the removal would push the count below
        ``PHOTO_COLLAGE_MIN_ITEMS``. Raises
        :class:`CollageItemsMismatchError` if ``item_id`` is not on
        the block — this is an application-layer EntityNotFound on
        the route, but at the domain layer we keep all collage-item
        identity errors in the same field-error family.
        """
        index = next(
            (i for i, it in enumerate(self.items) if it.oid == item_id),
            -1,
        )
        if index < 0:
            raise CollageItemsMismatchError()
        candidate = list(self.items)
        removed = candidate.pop(index)
        _validate_collage_items(candidate)
        self.items = candidate
        return removed.file_id

    def reorder_items(self, ordered_ids: list[CollageItemID]) -> None:
        """Reorder existing items by id.

        ``ordered_ids`` must be a permutation of the block's current
        item ids — same multiset, no additions, no omissions.
        Anything else raises :class:`CollageItemsMismatchError`;
        add/remove flows have their own dedicated commands.
        """
        existing_ids = [it.oid for it in self.items]
        if sorted(ordered_ids) != sorted(existing_ids):
            raise CollageItemsMismatchError()
        by_id = {it.oid: it for it in self.items}
        self.items = [by_id[oid] for oid in ordered_ids]

    def update_item_caption(
        self,
        item_id: CollageItemID,
        caption: CollageCaption | None,
    ) -> None:
        """Replace one item's caption (or clear it if ``caption`` is None).

        Raises :class:`CollageItemsMismatchError` if no item carries
        ``item_id``.
        """
        index = next(
            (i for i, it in enumerate(self.items) if it.oid == item_id),
            -1,
        )
        if index < 0:
            raise CollageItemsMismatchError()
        current = self.items[index]
        self.items[index] = CollageItem(
            oid=current.oid,
            file_id=current.file_id,
            caption=caption,
        )

    def update_title(self, new_title: BlockTitle | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: NoteLessonID,
        product_id: ProductID,
        items: list[CollageItem],
        position: int,
        title: BlockTitle | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            items=items,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


LessonBlock = (
    HtmlBlock
    | KatexBlock
    | RutubeVideoBlock
    | CodeBlock
    | SingleChoiceBlock
    | MultiChoiceBlock
    | TextInputBlock
    | FileBlock
    | VideoFileBlock
    | PhotoCollageBlock
)
