from typing import Final

HTML_BLOCK_MAX_LEN: Final = 50_000
KATEX_BLOCK_MAX_LEN: Final = 50_000

VIDEO_TITLE_MAX_LEN: Final = 200

# Rutube video id is exactly 32 lowercase hex chars (md5-like).
RUTUBE_VIDEO_ID_LENGTH: Final = 32

# Code block: up to 200K chars of source per tab. Larger than HTML/KaTeX
# because a realistic snippet can span several screens of code, but
# bounded so a single tab can't blow up the whole payload.
CODE_BLOCK_MAX_LEN: Final = 200_000
# Backing column for the language token (`tsx`, `bash`, …). 16 chars is
# enough headroom for any plausible identifier without forcing a DB-level
# enum that would need a migration on every new language.
CODE_LANGUAGE_MAX_LEN: Final = 16
# Tab label visible to authors (`npm`, `pnpm`, `yarn`, `Component.tsx`).
# Short by design — multi-tab blocks are for variant snippets, not titles.
CODE_TAB_LABEL_MAX_LEN: Final = 32
# Hard cap on how many tabs a single block may carry. Anything above ~8
# stops being a legible variant picker and starts being a "do you really
# want a folder explorer?" — and we already have Lessons for that.
CODE_BLOCK_MAX_TABS: Final = 8

# Visible label for one option inside a choice block. Plain text only —
# rich content goes in the preceding HTML block; the option is just a
# radio/checkbox caption.
CHOICE_OPTION_LABEL_MAX_LEN: Final = 200
# A choice question only makes sense with at least two options.
CHOICE_BLOCK_MIN_OPTIONS: Final = 2
# Hard cap on options. More than ~8 stops being a "pick one/several" UX
# and becomes a poor-man's dropdown — at which point a different block
# type would be the honest answer.
CHOICE_BLOCK_MAX_OPTIONS: Final = 8

# Accepted answer for a text-input block. Short by design — comparison
# is exact-match after normalisation, not free-form review, so multi-
# sentence answers don't fit the model.
TEXT_INPUT_ANSWER_MAX_LEN: Final = 500
# Author must provide at least one accepted answer.
TEXT_INPUT_MIN_ACCEPTED: Final = 1
# Hard cap on accepted-answer list — 10 synonyms covers realistic
# variants (case/spelling) without becoming an unmaintainable list.
TEXT_INPUT_MAX_ACCEPTED: Final = 10

# Shared title cap for file / video-file / photo-collage blocks. Kept
# separate from VIDEO_TITLE_MAX_LEN so the Rutube path stays untouched
# and the three new block types share one knob.
BLOCK_TITLE_MAX_LEN: Final = 200
# Caption shown under one photo inside a collage. Bounded to avoid a
# photo collage devolving into a long-form text wall — that's what an
# HTML block is for.
PHOTO_COLLAGE_CAPTION_MAX_LEN: Final = 280
# Photo collage must carry at least one item — a zero-photo collage
# is meaningless.
PHOTO_COLLAGE_MIN_ITEMS: Final = 1
# Hard cap on photos per collage. 12 covers realistic gallery sizes
# (a 3x4 grid) without producing a layout the editor can't render
# legibly.
PHOTO_COLLAGE_MAX_ITEMS: Final = 12
