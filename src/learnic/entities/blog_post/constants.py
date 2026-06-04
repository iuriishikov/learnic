from typing import Final

# Human-readable post title shown in lists and as the page heading.
BLOG_POST_TITLE_MAX_LEN: Final = 200

# URL-friendly slug used in the public path (`/blog/posts/{slug}`).
# Lowercase alphanumerics separated by single hyphens — see
# ``BlogPostSlug`` for the exact pattern. Min length keeps slugs
# meaningful (no single-character URLs); max mirrors the title cap so
# an auto-suggested slug derived from the title always fits.
BLOG_POST_SLUG_MIN_LEN: Final = 3
BLOG_POST_SLUG_MAX_LEN: Final = 200
