import json
import math
import re
from typing import Any, ClassVar, Self

from learnic.entities.common.value_object import ValueObject
from learnic.entities.note_block.constants import (
    BLOCK_TITLE_MAX_LEN,
    CHOICE_OPTION_LABEL_MAX_LEN,
    CODE_BLOCK_MAX_LEN,
    CODE_TAB_LABEL_MAX_LEN,
    FUNCTION_GRAPH_MAX_OBJECTS,
    FUNCTION_GRAPH_MAX_PARAMS,
    FUNCTION_GRAPH_SCHEMA_VERSION,
    GRAPH_AXIS_LABEL_MAX_LEN,
    GRAPH_CONFIG_MAX_LEN,
    GRAPH_EXPR_MAX_LEN,
    GRAPH_LABEL_MAX_LEN,
    GRAPH_PARAM_NAME_MAX_LEN,
    GRAPH_STYLE_COLOR_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    PHOTO_COLLAGE_CAPTION_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    TEXT_INPUT_ANSWER_MAX_LEN,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.note_block.enums import CodeBlockLanguage
from learnic.entities.note_block.errors import (
    BlockContentTooLongError,
    EmptyBlockContentError,
    GraphConfigTooLargeError,
    InvalidGraphConfigError,
    InvalidGraphParameterError,
    InvalidGraphViewportError,
    InvalidRutubeUrlError,
    TooManyGraphObjectsError,
    TooManyGraphParametersError,
    UnsafeGraphExpressionError,
    UnsupportedCodeLanguageError,
    UnsupportedGraphSchemaVersionError,
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


# Safe character set for client-evaluated expressions: digits, latin
# letters, ``_``, whitespace and the arithmetic operators / grouping
# / separators. Anything else (``[`` ``]`` ``{`` ``}`` ``;`` ``=`` ``:``
# backtick, …) is rejected so an authored expression can't smuggle code
# to the renderer.
_EXPR_PATTERN: re.Pattern[str] = re.compile(r"^[0-9A-Za-z_\s+\-*/^().,]*$")
_PARAM_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_OBJECT_KINDS: frozenset[str] = frozenset(
    {"function", "parametric", "implicit", "point", "segment", "vertical_line"},
)
_DASH_VALUES: frozenset[str] = frozenset({"solid", "dashed", "dotted"})


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


class GraphConfig(ValueObject):
    """Validated config payload of a :class:`FunctionGraphBlock`.

    Stored verbatim as one JSONB object mirroring the frontend
    ``GraphSpec`` (snake_case on the wire). The VO guarantees the DB
    only ever holds a structurally-sound, size-bounded config whose
    expression strings are restricted to a safe character set — they
    are evaluated client-side by the plotting engine (JSXGraph), never
    on the server, so the threat model is "don't persist a payload that
    lets the client do something unsafe". Empty ``objects`` is allowed:
    an author may add curves in the editor after creating the block.
    """

    value: dict[str, Any]

    def __post_init__(self) -> None:
        config = self.value
        if not isinstance(config, dict):
            raise InvalidGraphConfigError("not_object")
        self._ensure_size(config)
        self._ensure_schema(config)
        self._ensure_viewport(config.get("viewport"))
        self._ensure_axes(config.get("axes"))
        self._ensure_parameters(config.get("parameters"))
        self._ensure_objects(config.get("objects"))

    @staticmethod
    def _ensure_size(config: dict[str, Any]) -> None:
        try:
            encoded = json.dumps(config)
        except (TypeError, ValueError) as exc:
            raise InvalidGraphConfigError("not_serialisable") from exc
        if len(encoded) > GRAPH_CONFIG_MAX_LEN:
            raise GraphConfigTooLargeError(GRAPH_CONFIG_MAX_LEN)

    @staticmethod
    def _ensure_schema(config: dict[str, Any]) -> None:
        version = config.get("schema_version")
        if version != FUNCTION_GRAPH_SCHEMA_VERSION:
            raise UnsupportedGraphSchemaVersionError(
                version if isinstance(version, int) else 0,
            )

    @staticmethod
    def _ensure_viewport(viewport: Any) -> None:
        if not isinstance(viewport, dict):
            raise InvalidGraphViewportError("missing")
        bounds = {k: viewport.get(k) for k in ("x_min", "x_max", "y_min", "y_max")}
        if not all(_is_finite_number(v) for v in bounds.values()):
            raise InvalidGraphViewportError("not_finite")
        if bounds["x_min"] >= bounds["x_max"]:
            raise InvalidGraphViewportError("x_inverted")
        if bounds["y_min"] >= bounds["y_max"]:
            raise InvalidGraphViewportError("y_inverted")

    @staticmethod
    def _ensure_axes(axes: Any) -> None:
        if axes is None:
            return
        if not isinstance(axes, dict):
            raise InvalidGraphConfigError("axes")
        for key in ("x_label", "y_label"):
            label = axes.get(key)
            if label is not None and (
                not isinstance(label, str)
                or len(label) > GRAPH_AXIS_LABEL_MAX_LEN
            ):
                raise InvalidGraphConfigError("axis_label")

    @classmethod
    def _ensure_parameters(cls, parameters: Any) -> None:
        if parameters is None:
            return
        if not isinstance(parameters, list):
            raise InvalidGraphConfigError("parameters")
        if len(parameters) > FUNCTION_GRAPH_MAX_PARAMS:
            raise TooManyGraphParametersError(FUNCTION_GRAPH_MAX_PARAMS)
        seen: set[str] = set()
        for parameter in parameters:
            name = cls._ensure_parameter(parameter)
            if name in seen:
                raise InvalidGraphParameterError("duplicate")
            seen.add(name)

    @staticmethod
    def _ensure_parameter(parameter: Any) -> str:
        if not isinstance(parameter, dict):
            raise InvalidGraphParameterError("name")
        name = parameter.get("name")
        if (
            not isinstance(name, str)
            or len(name) > GRAPH_PARAM_NAME_MAX_LEN
            or _PARAM_NAME_PATTERN.match(name) is None
        ):
            raise InvalidGraphParameterError("name")
        low = parameter.get("min")
        high = parameter.get("max")
        value = parameter.get("value")
        if not all(_is_finite_number(v) for v in (low, high, value)):
            raise InvalidGraphParameterError("range")
        if not low <= value <= high:
            raise InvalidGraphParameterError("range")
        step = parameter.get("step")
        if not _is_finite_number(step) or step <= 0:
            raise InvalidGraphParameterError("step")
        return name

    @classmethod
    def _ensure_objects(cls, objects: Any) -> None:
        if not isinstance(objects, list):
            raise InvalidGraphConfigError("objects")
        if len(objects) > FUNCTION_GRAPH_MAX_OBJECTS:
            raise TooManyGraphObjectsError(FUNCTION_GRAPH_MAX_OBJECTS)
        for obj in objects:
            cls._ensure_object(obj)

    @classmethod
    def _ensure_object(cls, obj: Any) -> None:
        if not isinstance(obj, dict):
            raise InvalidGraphConfigError("object")
        kind = obj.get("kind")
        if kind not in _OBJECT_KINDS:
            raise InvalidGraphConfigError("kind")
        cls._ensure_label(obj.get("label"))
        cls._ensure_style(obj.get("style"))
        cls._ensure_geometry(kind, obj)

    @classmethod
    def _ensure_geometry(cls, kind: str, obj: dict[str, Any]) -> None:
        if kind == "function":
            cls._ensure_expr(obj.get("expr"))
            cls._ensure_optional_number(obj.get("domain_min"))
            cls._ensure_optional_number(obj.get("domain_max"))
        elif kind == "parametric":
            cls._ensure_expr(obj.get("x_expr"))
            cls._ensure_expr(obj.get("y_expr"))
            cls._ensure_number(obj.get("t_min"))
            cls._ensure_number(obj.get("t_max"))
        elif kind == "implicit":
            cls._ensure_expr(obj.get("expr"))
        elif kind == "point":
            cls._ensure_scalar(obj.get("x"))
            cls._ensure_scalar(obj.get("y"))
        elif kind == "segment":
            for key in ("x1", "y1", "x2", "y2"):
                cls._ensure_scalar(obj.get(key))
        else:  # vertical_line
            cls._ensure_scalar(obj.get("x"))

    @staticmethod
    def _ensure_expr(expr: Any) -> None:
        if not isinstance(expr, str):
            raise UnsafeGraphExpressionError("chars")
        if len(expr) > GRAPH_EXPR_MAX_LEN:
            raise UnsafeGraphExpressionError("length")
        if _EXPR_PATTERN.match(expr) is None:
            raise UnsafeGraphExpressionError("chars")

    @classmethod
    def _ensure_scalar(cls, scalar: Any) -> None:
        # A coordinate is either a finite number or a safe expression
        # (it may reference parameters, e.g. ``"a"`` or ``"0.5*a+1"``).
        if _is_finite_number(scalar):
            return
        cls._ensure_expr(scalar)

    @staticmethod
    def _ensure_number(value: Any) -> None:
        if not _is_finite_number(value):
            raise InvalidGraphConfigError("number")

    @classmethod
    def _ensure_optional_number(cls, value: Any) -> None:
        if value is not None:
            cls._ensure_number(value)

    @staticmethod
    def _ensure_label(label: Any) -> None:
        if label is None:
            return
        if not isinstance(label, str) or len(label) > GRAPH_LABEL_MAX_LEN:
            raise InvalidGraphConfigError("label")

    @staticmethod
    def _ensure_style(style: Any) -> None:
        if style is None:
            return
        if not isinstance(style, dict):
            raise InvalidGraphConfigError("style")
        color = style.get("color")
        if color is not None and (
            not isinstance(color, str)
            or len(color) > GRAPH_STYLE_COLOR_MAX_LEN
        ):
            raise InvalidGraphConfigError("style_color")
        width = style.get("width")
        if width is not None and not _is_finite_number(width):
            raise InvalidGraphConfigError("style_width")
        dash = style.get("dash")
        if dash is not None and dash not in _DASH_VALUES:
            raise InvalidGraphConfigError("style_dash")
