import re
from typing import ClassVar, Self

from learnic.entities.common.value_object import ValueObject
from learnic.entities.course_block.constants import (
    BLOCK_TITLE_MAX_LEN,
    CHOICE_OPTION_LABEL_MAX_LEN,
    CODE_BLOCK_MAX_LEN,
    CODE_TAB_LABEL_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    PHOTO_COLLAGE_CAPTION_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    TEXT_INPUT_ANSWER_MAX_LEN,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.enums import CodeBlockLanguage
from learnic.entities.course_block.errors import (
    BlockContentTooLongError,
    EmptyBlockContentError,
    InvalidRutubeUrlError,
    UnsupportedCodeLanguageError,
)


class HtmlContent(ValueObject):
    """Sanitized HTML body of an :class:`HtmlBlock`.

    The VO enforces only the length invariant — sanitization is
    performed in the command handler via the ``HtmlSanitizer``
    Protocol BEFORE the VO is constructed. Length is measured
    after sanitization. Empty values are accepted: authors create
    blocks first and fill the body in the editor afterwards.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > HTML_BLOCK_MAX_LEN:
            raise BlockContentTooLongError("html", HTML_BLOCK_MAX_LEN)


class KatexSource(ValueObject):
    """Raw KaTeX math-source body of a :class:`KatexBlock`.

    KaTeX is a strict subset of LaTeX (math-mode focused); the
    full set of supported commands is at
    https://katex.org/docs/support_table.html. No server-side
    sanitization — KaTeX renders the body safely on the client.
    Length is capped to avoid pathological payloads. Empty / blank
    values are accepted: authors create blocks first and fill the
    source in the editor afterwards.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > KATEX_BLOCK_MAX_LEN:
            raise BlockContentTooLongError("source", KATEX_BLOCK_MAX_LEN)


class RutubeVideoID(ValueObject):
    """Rutube video identifier — 32 lowercase hex characters.

    Authors may submit either a bare id or a full URL; the static
    ``from_url`` parser extracts the id from URLs of the shape
    ``https://[www.]rutube.ru/video/{id}[/]``. The VO itself
    validates only the canonical id format — handlers should call
    ``from_url`` on user input first.
    """

    _ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9a-f]{32}$")
    _URL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^https?://(?:www\.)?rutube\.ru/video/(?P<id>[0-9a-fA-F]+)/?$",
    )

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != RUTUBE_VIDEO_ID_LENGTH or not self._ID_PATTERN.match(
            self.value,
        ):
            raise InvalidRutubeUrlError("invalid_id_format")

    @classmethod
    def from_url(cls, url: str) -> Self:
        """Parse a Rutube video URL into the canonical 32-hex id."""
        if not url or not url.strip():
            raise InvalidRutubeUrlError("empty")
        match = cls._URL_PATTERN.match(url.strip())
        if match is None:
            raise InvalidRutubeUrlError("unsupported_host")
        raw_id = match.group("id")
        if len(raw_id) != RUTUBE_VIDEO_ID_LENGTH:
            raise InvalidRutubeUrlError("missing_id")
        return cls(raw_id.lower())


class VideoTitle(ValueObject):
    """Optional human-readable caption for a :class:`RutubeVideoBlock`."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlockContentError("title")
        if len(self.value) > VIDEO_TITLE_MAX_LEN:
            raise BlockContentTooLongError("title", VIDEO_TITLE_MAX_LEN)


class CodeSource(ValueObject):
    """Raw source body of a :class:`CodeBlock`.

    Whitespace is preserved verbatim — code is meaningful as-is —
    so empty / blank values are accepted (an author may create the
    block first and fill the body in the editor). Only an upper
    length bound is enforced.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > CODE_BLOCK_MAX_LEN:
            raise BlockContentTooLongError("source", CODE_BLOCK_MAX_LEN)


class CodeLanguage(ValueObject):
    """Syntax-highlighting language tag for a code tab.

    Values are bound to :class:`CodeBlockLanguage` — anything else
    is rejected at the entity boundary so the frontend tokenizer
    can never face an unknown token.
    """

    value: str

    def __post_init__(self) -> None:
        try:
            CodeBlockLanguage(self.value)
        except ValueError as exc:
            raise UnsupportedCodeLanguageError(self.value) from exc


class CodeTabLabel(ValueObject):
    """Author-facing label for a tab inside a multi-tab code block.

    Empty string is allowed — single-tab blocks render without a
    visible tab strip and don't need a label. For multi-tab blocks
    the entity-level invariant requires every label to be non-empty
    and unique, see :class:`CodeBlock`.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > CODE_TAB_LABEL_MAX_LEN:
            raise BlockContentTooLongError("label", CODE_TAB_LABEL_MAX_LEN)


class ChoiceOptionLabel(ValueObject):
    """Visible caption for one option inside a choice block.

    Plain text — the question prompt (rich content) lives in the
    preceding HTML block, the option itself is just a radio /
    checkbox caption. Stored verbatim; newlines are tolerated but
    discouraged (the frontend renders the label single-line by
    default). Empty / blank labels are accepted: a freshly created
    block ships with placeholder options the author fills in
    afterwards. Cross-option uniqueness lives on the parent block
    and tolerates empty placeholders.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > CHOICE_OPTION_LABEL_MAX_LEN:
            raise BlockContentTooLongError(
                "option_label",
                CHOICE_OPTION_LABEL_MAX_LEN,
            )


class BlockTitle(ValueObject):
    """Optional human-readable title for a file / video-file / collage block.

    Shared across the three file-backed block types — they all expose the
    same "small caption above the asset" affordance and there is no
    block-type-specific invariant on a title.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlockContentError("title")
        if len(self.value) > BLOCK_TITLE_MAX_LEN:
            raise BlockContentTooLongError("title", BLOCK_TITLE_MAX_LEN)


class CollageCaption(ValueObject):
    """Optional caption attached to one photo inside a collage.

    Captions are short by design — anything longer belongs in an HTML
    block placed adjacent to the collage.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlockContentError("caption")
        if len(self.value) > PHOTO_COLLAGE_CAPTION_MAX_LEN:
            raise BlockContentTooLongError(
                "caption",
                PHOTO_COLLAGE_CAPTION_MAX_LEN,
            )


class AcceptedAnswer(ValueObject):
    """One accepted answer for a text-input block, stored verbatim.

    Normalisation (case folding, whitespace trimming) is applied at
    check-time per the parent block's flags — the VO stores raw
    author input so an author can later flip a flag without losing
    fidelity. Empty / blank values are accepted: a freshly created
    block ships with a placeholder answer the author fills in
    afterwards. Cross-answer uniqueness lives on the parent block
    and tolerates empty placeholders.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > TEXT_INPUT_ANSWER_MAX_LEN:
            raise BlockContentTooLongError(
                "accepted_answer",
                TEXT_INPUT_ANSWER_MAX_LEN,
            )
