from typing import Protocol


class HtmlSanitizer(Protocol):
    """Strips unsafe HTML (``<script>``, inline event handlers, etc.).

    Implementations keep a conservative whitelist of tags, attributes and
    URL schemes. Command handlers must call ``sanitize(...)`` on any
    user-supplied HTML **before** wrapping it in a value object — the VO
    only enforces length, not HTML safety.
    """

    async def sanitize(self, raw: str) -> str:
        """Return ``raw`` with unsafe markup removed.

        Awaitable so the synchronous HTML parser runs off the event loop
        (the adapter offloads it to a worker thread).
        """
        ...
