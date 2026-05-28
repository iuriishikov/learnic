from typing import Final

from fastapi import Request

from learnic.application.common.security.refresh_tokens import DeviceContext

_USER_AGENT_MAX_LEN: Final = 512
_DEVICE_LABEL_MAX_LEN: Final = 128

_BROWSERS: Final[tuple[tuple[str, str], ...]] = (
    ("edg/", "Edge"),
    ("opr/", "Opera"),
    ("opera", "Opera"),
    ("firefox/", "Firefox"),
    ("chrome/", "Chrome"),
    ("crios/", "Chrome"),
    ("fxios/", "Firefox"),
    ("safari/", "Safari"),
)

_OPERATING_SYSTEMS: Final[tuple[tuple[str, str], ...]] = (
    ("iphone", "iOS"),
    ("ipad", "iPadOS"),
    ("ipod", "iOS"),
    ("android", "Android"),
    ("windows", "Windows"),
    ("mac os x", "macOS"),
    ("macintosh", "macOS"),
    ("cros", "ChromeOS"),
    ("linux", "Linux"),
)


def parse_device_label(user_agent: str | None) -> str | None:
    """Best-effort short label like ``"Chrome on macOS"``.

    Heuristic-only — a richer parser belongs in a dedicated library;
    this exists so the active-sessions UI has something readable to
    show without a new runtime dependency.
    """
    if not user_agent:
        return None

    ua = user_agent.lower()
    browser: str | None = None
    for needle, name in _BROWSERS:
        if needle in ua:
            # "chrome/" appears in Edge/Opera UA strings — skip it when
            # a more specific match was already found.
            if name == "Chrome" and ("edg/" in ua or "opr/" in ua):
                continue
            # "safari/" appears in every Chromium UA — only credit Safari
            # when neither Chrome nor Edge is present.
            if name == "Safari" and ("chrome/" in ua or "crios/" in ua):
                continue
            browser = name
            break

    operating_system: str | None = None
    for needle, name in _OPERATING_SYSTEMS:
        if needle in ua:
            operating_system = name
            break

    if browser is None and operating_system is None:
        return None
    if browser is None:
        return operating_system
    if operating_system is None:
        return browser
    return f"{browser} on {operating_system}"


def client_ip(request: Request) -> str | None:
    """Best-effort originating client IP, honouring proxy headers.

    Prefers ``X-Forwarded-For`` (first hop) then ``X-Real-IP`` so the
    captured address is the real client when the API sits behind a
    reverse proxy / load balancer; falls back to the socket peer.
    Returns ``None`` when nothing usable is present.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry is the originating client; later entries are proxies.
        candidate = forwarded.split(",", 1)[0].strip()
        if candidate:
            return candidate
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip() or None
    if request.client is not None and request.client.host:
        return request.client.host
    return None


def device_from_request(request: Request) -> DeviceContext:
    """Extract IP, User-Agent and a short device label from ``request``.

    Truncates the raw User-Agent to the column width so a hostile
    client cannot blow up the row. Honours ``X-Forwarded-For`` /
    ``X-Real-IP`` so the captured IP is the originating client when
    the API is fronted by a reverse proxy.
    """
    user_agent = request.headers.get("user-agent")
    if user_agent is not None:
        user_agent = user_agent[:_USER_AGENT_MAX_LEN]
    label = parse_device_label(user_agent)
    if label is not None:
        label = label[:_DEVICE_LABEL_MAX_LEN]
    return DeviceContext(
        ip_address=client_ip(request),
        user_agent=user_agent,
        device_label=label,
    )
