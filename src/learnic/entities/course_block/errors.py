from learnic.entities.common.errors import FieldError


class EmptyBlockContentError(FieldError):
    """Raised when a block's body is empty after construction."""

    field: str


class BlockContentTooLongError(FieldError):
    """Raised when a block's body exceeds its max length."""

    field: str
    limit: int


class InvalidRutubeUrlError(FieldError):
    """Raised when a string can't be parsed as a Rutube video URL.

    ``reason`` is one of ``"empty"``, ``"unsupported_host"``,
    ``"missing_id"``, ``"invalid_id_format"``.
    """

    reason: str


class UnsupportedCodeLanguageError(FieldError):
    """Raised when a :class:`CodeBlock` language token isn't supported.

    The supported set is bounded by the frontend tokenizer — see
    :class:`CodeBlockLanguage`.
    """

    value: str


class EmptyCodeTabsError(FieldError):
    """Raised when a :class:`CodeBlock` is constructed with zero tabs.

    Every code block must carry at least one tab — a "tab-less" block
    has no source to render.
    """


class TooManyCodeTabsError(FieldError):
    """Raised when a :class:`CodeBlock` exceeds ``CODE_BLOCK_MAX_TABS``."""

    limit: int


class DuplicateCodeTabLabelError(FieldError):
    """Raised when two tabs in a multi-tab block share the same label.

    Single-tab blocks may have an empty label. For multi-tab blocks
    every label must be non-empty and unique so the tab strip can
    address tabs by label without collision.
    """

    label: str


class TooFewChoiceOptionsError(FieldError):
    """Raised when a choice block has fewer options than the lower bound."""

    limit: int


class TooManyChoiceOptionsError(FieldError):
    """Raised when a choice block exceeds ``CHOICE_BLOCK_MAX_OPTIONS``."""

    limit: int


class DuplicateChoiceOptionLabelError(FieldError):
    """Raised when two options inside one choice block share a label."""

    label: str


class DuplicateChoiceOptionIdError(FieldError):
    """Raised when two options inside one choice block share an id.

    Option ids are domain-generated UUIDs; a collision indicates a
    serialization/load bug (e.g. the snapshotter copied an id
    instead of regenerating). Surface it loudly.
    """

    option_id: str


class CorrectOptionNotInOptionsError(FieldError):
    """Raised when a single-choice block's correct id is not in its options."""

    option_id: str


class MultipleCorrectOptionsInSingleChoiceError(FieldError):
    """Raised when a single-choice payload marks more than one option correct.

    Single-choice is a closed-set invariant: exactly one option is
    correct. The author either picks one (single-choice) or several
    (multi-choice block type). Two correct options would be ambiguous.
    """

    count: int


class EmptyCorrectOptionsError(FieldError):
    """Raised when a multi-choice block has no correct options.

    A multi-choice question with zero correct answers is undecidable —
    every submission would be wrong, including the empty one.
    """


class CorrectOptionsNotSubsetError(FieldError):
    """Raised when a multi-choice block's correct ids are not in options."""

    option_ids: tuple[str, ...]


class TooFewAcceptedAnswersError(FieldError):
    """Raised when a text-input block has no accepted answers."""

    limit: int


class TooManyAcceptedAnswersError(FieldError):
    """Raised when a text-input block exceeds ``TEXT_INPUT_MAX_ACCEPTED``."""

    limit: int


class DuplicateAcceptedAnswerError(FieldError):
    """Raised when two accepted answers in a text-input block are identical.

    Identity is checked under the block's own normalisation flags
    (``case_sensitive`` / ``trim_whitespace``) — two raw strings that
    differ only in trailing whitespace collide when trim is on.
    """

    value: str


class TooFewCollageItemsError(FieldError):
    """Raised when a photo collage has fewer items than the lower bound."""

    limit: int


class TooManyCollageItemsError(FieldError):
    """Raised when a photo collage exceeds ``PHOTO_COLLAGE_MAX_ITEMS``."""

    limit: int


class CollageItemsMismatchError(FieldError):
    """Raised when a reorder payload doesn't cover the block's items exactly.

    The reorder operation requires the ``ordered_ids`` argument to be
    a permutation of the block's existing item ids — same set, no
    additions, no omissions. Anything else is ambiguous (is the SPA
    trying to drop an item? add one? the dedicated endpoints exist
    for that) and surfaces here.
    """
