from typing import Final

TAG_NAME_MIN_LEN: Final = 1
TAG_NAME_MAX_LEN: Final = 30

# Upper bound is loose because the wire format may carry any
# Pydantic-Color-accepted value: hex (`#ff0000`), named CSS color,
# `rgb()`/`rgba()`/`hsl()`/`hsla()` strings. ``50`` comfortably fits
# the longest realistic form (`rgba(255, 255, 255, 0.123)`).
TAG_COLOR_MAX_LEN: Final = 50

# Per-product cap. The list is rewritten in full on every
# ``PUT /products/{product_id}/tags``; longer lists make the
# autocomplete UX feel cluttered without adding domain value.
PRODUCT_TAGS_MAX: Final = 5
