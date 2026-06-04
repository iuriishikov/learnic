from typing import Final

# Sanitized HTML body of an HTML block. Matches the note HTML block
# cap — generous enough for a long rich-text section, bounded so a
# single block can't blow up the payload.
BLOG_HTML_BLOCK_MAX_LEN: Final = 50_000

# Optional author-facing caption shared by image and video blocks
# (image caption / video title). Short by design — long-form prose
# belongs in an adjacent HTML block.
BLOG_BLOCK_CAPTION_MAX_LEN: Final = 280
