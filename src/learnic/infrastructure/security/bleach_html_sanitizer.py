import asyncio
from collections.abc import Iterator
from typing import Any, Final

from bleach.html5lib_shim import Filter
from bleach.sanitizer import Cleaner
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


class _NoopenerFilter(Filter):  # type: ignore[misc]
    """Force ``rel="noopener noreferrer"`` on every ``<a target="_blank">``.

    ``bleach.clean`` keeps the ``target`` attribute but does not add
    ``rel``, leaving anchors open to reverse tabnabbing (the opened page
    can navigate the source tab via ``window.opener``). This html5lib
    filter runs after sanitization and rewrites the ``rel`` of any
    ``_blank`` anchor.
    """

    @override
    def __iter__(self) -> Iterator[Any]:
        for token in Filter.__iter__(self):
            if token.get("type") in {"StartTag", "EmptyTag"} and (
                token.get("name") == "a"
            ):
                attrs = token.get("data") or {}
                if attrs.get((None, "target")) == "_blank":
                    attrs[(None, "rel")] = "noopener noreferrer"
                    token["data"] = attrs
            yield token


_CLEANER: Final = Cleaner(
    tags=_ALLOWED_TAGS,
    attributes=_ALLOWED_ATTRIBUTES,
    protocols=_ALLOWED_PROTOCOLS,
    strip=True,
    strip_comments=True,
    filters=[_NoopenerFilter],
)


class BleachHtmlSanitizer(HtmlSanitizer):
    """Whitelist-based HTML sanitizer backed by ``bleach``.

    Unknown tags and attributes are dropped; unsafe URL schemes
    (``javascript:``, ``data:``) are rejected. Any text content
    outside the whitelist of tags survives as plain text so the
    document reads sensibly even after sanitization. External
    ``target="_blank"`` links get ``rel="noopener noreferrer"`` forced
    on them.

    ``bleach`` is a synchronous, CPU-bound HTML parser, so ``sanitize``
    offloads the work to a worker thread to keep the event loop free.
    """

    @override
    async def sanitize(self, raw: str) -> str:
        return await asyncio.to_thread(self._sanitize_sync, raw)

    def _sanitize_sync(self, raw: str) -> str:
        cleaned: str = _CLEANER.clean(raw)
        return cleaned
