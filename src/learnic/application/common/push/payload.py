from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PushPayload:
    """Cross-vendor envelope shipped to the browser over Web Push.

    Render-only — the Service Worker reads ``title`` / ``body``
    straight into ``self.registration.showNotification(...)``. The
    optional ``url`` is consumed by ``notificationclick`` to focus
    or open the right tab; ``tag`` enables in-place replacement of
    a previously-shown notification (so a click that marks a row
    read replaces the system banner instead of stacking another).
    """

    title: str
    body: str
    url: str | None = None
    tag: str | None = None
    icon: str | None = None
