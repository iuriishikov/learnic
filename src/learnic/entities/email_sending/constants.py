from datetime import timedelta
from typing import Final

MAX_EMAILS_PER_USER: Final = 50
"""Maximum number of user-initiated emails one account may trigger
within :data:`EMAIL_SEND_RATE_LIMIT_WINDOW`. Tune this to taste —
it is the single knob for the per-user outbound-email cap."""

EMAIL_SEND_RATE_LIMIT_WINDOW: Final = timedelta(hours=1)
"""Rolling window over which :data:`MAX_EMAILS_PER_USER` is counted."""

IP_MAX_LEN: Final = 45
"""Column width for the logged client IP — fits a full IPv6 textual
form (max 45 chars). Longer / hostile values are truncated before
insert so a crafted ``X-Forwarded-For`` cannot overflow the column."""
