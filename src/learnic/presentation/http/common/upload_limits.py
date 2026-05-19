"""Per-call-site upload caps for HTTP routes that read ``UploadFile``.

There is intentionally **no** single global ``MAX_FILE_SIZE_BYTES``
constant: every route reading an upload must import the constant
matching its own use case and pass it to
:func:`learnic.presentation.http.common.uploads.read_upload` as
``max_bytes=...``. The keyword-only ``max_bytes`` parameter has no
default, so omitting it is a ``TypeError`` at runtime and a mypy
error at static-analysis time — there is no way to upload "the
default amount".

Each constant below is named after the call-site it governs. When
the policy for a single surface changes, edit one value in one place
— consumers update automatically without a release-wide audit.

Caveats:

* The cap is enforced **after** the ASGI server has accepted the
  request body. There is no protection here against the network
  transferring the entire over-cap payload; combine with an upstream
  reverse-proxy body limit (Caddy / NGINX) when DOS is a concern.
* ``read_upload`` reads ``max_bytes + 1`` bytes and rejects on
  ``> max_bytes`` — anything bigger never lands in memory beyond
  that single extra byte.
"""

from typing import Final

_MB: Final = 1024 * 1024

# ---- profile / product chrome (small images, conservative caps) ---- #

# Avatar — single small portrait. Keep tight: a 5 MB cap covers any
# realistic JPEG/PNG, and oversized uploads usually mean "user picked
# the wrong file" rather than a legit need.
USER_AVATAR_MAX_BYTES: Final = 5 * _MB
# Cover — landscape banner. Slightly larger than avatar to leave room
# for higher-res screenshots / mockups, still image-only.
USER_COVER_MAX_BYTES: Final = 10 * _MB
# CV-timeline icon — almost always a small square logo / favicon.
USER_EXPERIENCE_ICON_MAX_BYTES: Final = 2 * _MB
# Product cover (the marketplace card image).
PRODUCT_COVER_MAX_BYTES: Final = 10 * _MB

# ---- lesson-content blocks (per-author-creativity caps) ---- #

# Generic file block — PDFs / slide decks / small archives. 50 MB
# covers the typical course material; anything heavier should live on
# an external CDN and be linked rather than re-hosted.
LESSON_FILE_BLOCK_MAX_BYTES: Final = 50 * _MB
# Video block — a single lecture or demo. 1 GiB covers ~30 min of
# 1080p H.264 at sane bitrates; longer cuts should be split into
# multiple lessons.
LESSON_VIDEO_BLOCK_MAX_BYTES: Final = 1024 * _MB
# Photo collage — a single item. 80 MB per photo accommodates RAW /
# high-resolution exports. The block-level item count is capped at
# 12, so the whole collage payload tops out below 1 GiB.
LESSON_COLLAGE_ITEM_MAX_BYTES: Final = 80 * _MB
