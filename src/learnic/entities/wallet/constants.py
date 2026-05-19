from typing import Final

# Sums are stored as integer minor units (kopecks for RUB).
# Upper bound guards against integer overflow and absurd typos —
# 10**12 kopecks == 10 billion RUB, far above any plausible movement.
MAX_AMOUNT: Final = 10**12

# Platform commission as integer per-mille of the price.
# 100 per-mille == 10.0%. Integer math keeps splits exact, no floats.
PLATFORM_COMMISSION_PERMILLE: Final = 100
COMMISSION_PERMILLE_DENOMINATOR: Final = 1000

# LedgerEntry.idempotency_key is bounded so that the DB index stays small
# and external systems (payment provider payment IDs, support ticket IDs)
# fit comfortably within the limit.
IDEMPOTENCY_KEY_MAX_LEN: Final = 128
