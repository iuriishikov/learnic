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
