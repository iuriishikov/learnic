import pytest

from learnic.entities.course_block.constants import (
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.errors import (
    BlockContentTooLongError,
    EmptyBlockContentError,
    InvalidRutubeUrlError,
)
from learnic.entities.course_block.value_objects import (
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
