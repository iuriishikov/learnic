from typing import Final

import bleach
from typing_extensions import override

from learnic.application.common.security.html import HtmlSanitizer

_ALLOWED_TAGS: Final[frozenset[str]] = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "u",
        "s",
        "code",
        "pre",
        "blockquote",
        "ul",
        "ol",
        "li",
        "a",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "span",
    }
)

_ALLOWED_ATTRIBUTES: Final[dict[str, list[str]]] = {
    "a": ["href", "title", "rel", "target"],
}

_ALLOWED_PROTOCOLS: Final[list[str]] = ["http", "https", "mailto"]


class BleachHtmlSanitizer(HtmlSanitizer):
    """Whitelist-based HTML sanitizer backed by ``bleach.clean``.

    Unknown tags and attributes are dropped; unsafe URL schemes
    (``javascript:``, ``data:``) are rejected. Any text content
    outside the whitelist of tags survives as plain text so the
    document reads sensibly even after sanitization.
    """

    @override
    def sanitize(self, raw: str) -> str:
        cleaned: str = bleach.clean(
            raw,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRIBUTES,
            protocols=_ALLOWED_PROTOCOLS,
            strip=True,
            strip_comments=True,
        )
        return cleaned
