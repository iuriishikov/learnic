import pytest

from learnic.entities.course_block.constants import (
    CHOICE_OPTION_LABEL_MAX_LEN,
    CODE_BLOCK_MAX_LEN,
    CODE_TAB_LABEL_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    TEXT_INPUT_ANSWER_MAX_LEN,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.errors import (
    BlockContentTooLongError,
    EmptyBlockContentError,
    InvalidRutubeUrlError,
    UnsupportedCodeLanguageError,
)
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


_VALID_ID = "f9bb1e0bdfac28c93c2c35a45f87f3eb"
_VALID_URL = f"https://rutube.ru/video/{_VALID_ID}/"


class TestHtmlContent:
    def test_accepts_valid(self) -> None:
        assert HtmlContent("<p>hi</p>").value == "<p>hi</p>"

    def test_rejects_empty(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            HtmlContent("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            HtmlContent("x" * (HTML_BLOCK_MAX_LEN + 1))


class TestKatexSource:
    def test_accepts_valid(self) -> None:
        assert KatexSource("E = mc^2").value == "E = mc^2"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            KatexSource("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            KatexSource("x" * (KATEX_BLOCK_MAX_LEN + 1))


class TestRutubeVideoID:
    def test_accepts_canonical_id(self) -> None:
        assert RutubeVideoID(_VALID_ID).value == _VALID_ID

    def test_rejects_short_id(self) -> None:
        with pytest.raises(InvalidRutubeUrlError):
            RutubeVideoID("abc")

    def test_rejects_non_hex(self) -> None:
        with pytest.raises(InvalidRutubeUrlError):
            RutubeVideoID("z" * 32)

    def test_from_url_extracts_id(self) -> None:
        assert RutubeVideoID.from_url(_VALID_URL).value == _VALID_ID

    def test_from_url_no_trailing_slash(self) -> None:
        assert (
            RutubeVideoID.from_url(f"https://rutube.ru/video/{_VALID_ID}").value
            == _VALID_ID
        )

    def test_from_url_with_www(self) -> None:
        assert (
            RutubeVideoID.from_url(f"https://www.rutube.ru/video/{_VALID_ID}/").value
            == _VALID_ID
        )

    def test_from_url_lowercases_id(self) -> None:
        upper_id = "F9BB1E0BDFAC28C93C2C35A45F87F3EB"
        result = RutubeVideoID.from_url(f"https://rutube.ru/video/{upper_id}/")
        assert result.value == upper_id.lower()

    def test_from_url_rejects_empty(self) -> None:
        with pytest.raises(InvalidRutubeUrlError) as exc:
            RutubeVideoID.from_url("")
        assert exc.value.reason == "empty"

    def test_from_url_rejects_youtube(self) -> None:
        with pytest.raises(InvalidRutubeUrlError) as exc:
            RutubeVideoID.from_url("https://youtube.com/watch?v=abc")
        assert exc.value.reason == "unsupported_host"

    def test_from_url_rejects_short_id(self) -> None:
        with pytest.raises(InvalidRutubeUrlError):
            RutubeVideoID.from_url("https://rutube.ru/video/short/")


class TestVideoTitle:
    def test_accepts_valid(self) -> None:
        assert VideoTitle("Lecture 1").value == "Lecture 1"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            VideoTitle("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            VideoTitle("x" * (VIDEO_TITLE_MAX_LEN + 1))


class TestCodeSource:
    def test_accepts_non_empty(self) -> None:
        assert CodeSource("const x = 1;").value == "const x = 1;"

    def test_accepts_empty_for_freshly_created_block(self) -> None:
        # Empty code is fine — the author may add the block first and
        # type code in the editor afterwards.
        assert CodeSource("").value == ""

    def test_preserves_whitespace(self) -> None:
        # Whitespace is meaningful in code; the VO must not strip it.
        assert CodeSource("  \n  \t").value == "  \n  \t"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            CodeSource("x" * (CODE_BLOCK_MAX_LEN + 1))


class TestCodeLanguage:
    def test_accepts_supported(self) -> None:
        # Round-trip every backend-recognised language — guards against
        # accidental enum drift from the frontend tokenizer's supported
        # set (the two MUST stay in sync per the enum's docstring).
        supported = (
            "tsx", "ts", "jsx", "js",
            "python", "go", "rust", "java", "kotlin", "swift", "php", "ruby",
            "c", "cpp", "csharp",
            "html", "xml", "css", "scss",
            "json", "yaml", "toml", "sql", "graphql",
            "markdown",
            "bash", "sh", "dockerfile",
            "plain",
        )
        for lang in supported:
            assert CodeLanguage(lang).value == lang

    def test_rejects_unsupported(self) -> None:
        # Use a language we explicitly don't ship — "haskell" is a stable
        # canary because adding it would also need a tokenizer landing
        # client-side first (per the enum's docstring contract).
        with pytest.raises(UnsupportedCodeLanguageError):
            CodeLanguage("haskell")

    def test_rejects_empty(self) -> None:
        with pytest.raises(UnsupportedCodeLanguageError):
            CodeLanguage("")


class TestCodeTabLabel:
    def test_accepts_empty(self) -> None:
        # Empty label is meaningful for single-tab blocks (the strip
        # is hidden client-side). Cross-tab uniqueness is enforced
        # at the entity level, not the VO level.
        assert CodeTabLabel("").value == ""

    def test_accepts_typical_labels(self) -> None:
        for label in ("npm", "pnpm", "yarn", "Component.tsx"):
            assert CodeTabLabel(label).value == label

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            CodeTabLabel("x" * (CODE_TAB_LABEL_MAX_LEN + 1))


class TestChoiceOptionLabel:
    def test_accepts_typical(self) -> None:
        assert ChoiceOptionLabel("Yes").value == "Yes"

    def test_rejects_empty(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            ChoiceOptionLabel("")

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            ChoiceOptionLabel("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            ChoiceOptionLabel("x" * (CHOICE_OPTION_LABEL_MAX_LEN + 1))


class TestAcceptedAnswer:
    def test_accepts_typical(self) -> None:
        assert AcceptedAnswer("Paris").value == "Paris"

    def test_preserves_whitespace_for_later_normalisation(self) -> None:
        # The VO stores raw input; the block's check-time normalisation
        # decides what to do with surrounding whitespace.
        assert AcceptedAnswer(" Paris ").value == " Paris "

    def test_rejects_empty(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            AcceptedAnswer("")

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyBlockContentError):
            AcceptedAnswer("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(BlockContentTooLongError):
            AcceptedAnswer("x" * (TEXT_INPUT_ANSWER_MAX_LEN + 1))
