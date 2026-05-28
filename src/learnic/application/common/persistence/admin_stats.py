from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class AdminStatsView:
    """Platform-wide aggregate counters for the admin dashboard.

    Most fields are a simple ``COUNT(*)`` over a single table slice;
    ``dau`` / ``mau`` are ``COUNT(DISTINCT actor_id)`` over the
    ``site_visit`` activity events in a rolling 1-day / 30-day window.
    Cheap enough to compute on demand for an MVP-scale dashboard — as
    the platform grows these can move behind a materialised view or a
    periodically-refreshed cache without changing this contract.
    """

    total_users: int
    banned_users: int
    admin_users: int
    total_courses: int
    draft_courses: int
    published_courses: int
    archived_courses: int
    total_enrollments: int
    active_enrollments: int
    dau: int
    mau: int


class AdminStatsReader(Protocol):
    """Read-side source of the admin dashboard counters."""

    async def collect(self) -> AdminStatsView:
        """Return a freshly-computed snapshot of platform counters."""
        ...
