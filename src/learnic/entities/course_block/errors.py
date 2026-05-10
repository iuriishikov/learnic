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
