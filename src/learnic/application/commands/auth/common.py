from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class TokenPair:
    """Access + refresh tokens returned by login/refresh/verify-wait."""

    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
