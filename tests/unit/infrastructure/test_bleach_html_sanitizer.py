import pytest

from learnic.infrastructure.security.bleach_html_sanitizer import (
    BleachHtmlSanitizer,
)


@pytest.fixture
def sanitizer() -> BleachHtmlSanitizer:
    return BleachHtmlSanitizer()


def test_keeps_allowed_tags(sanitizer: BleachHtmlSanitizer) -> None:
    assert sanitizer.sanitize("<p>hi</p>") == "<p>hi</p>"
    assert sanitizer.sanitize("<strong>x</strong>") == "<strong>x</strong>"


def test_strips_script_tags(sanitizer: BleachHtmlSanitizer) -> None:
    cleaned = sanitizer.sanitize("<p>ok</p><script>alert(1)</script>")
    # Tag is gone → browser cannot execute. Text content ("alert(1)")
    # may survive as inert plain text; that's safe (no script context).
    assert "<script" not in cleaned
    assert "</script>" not in cleaned
    assert "<p>ok</p>" in cleaned


def test_strips_inline_event_handlers(sanitizer: BleachHtmlSanitizer) -> None:
    cleaned = sanitizer.sanitize('<p onclick="bad()">hi</p>')
    assert "onclick" not in cleaned
    assert "bad()" not in cleaned


def test_strips_javascript_protocol_in_links(
    sanitizer: BleachHtmlSanitizer,
) -> None:
    cleaned = sanitizer.sanitize('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in cleaned


def test_keeps_http_and_https_links(sanitizer: BleachHtmlSanitizer) -> None:
    cleaned = sanitizer.sanitize('<a href="https://ok.test">ok</a>')
    assert 'href="https://ok.test"' in cleaned


def test_strips_iframe(sanitizer: BleachHtmlSanitizer) -> None:
    cleaned = sanitizer.sanitize('<iframe src="evil"></iframe>')
    assert "<iframe" not in cleaned


def test_strips_img_with_onerror(sanitizer: BleachHtmlSanitizer) -> None:
    cleaned = sanitizer.sanitize('<img src=x onerror="alert(1)">')
    # <img> not in allowed tags, gets stripped entirely
    assert "<img" not in cleaned
    assert "onerror" not in cleaned
