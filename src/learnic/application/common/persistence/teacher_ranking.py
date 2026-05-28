from dataclasses import dataclass
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class TopTeacherView:
    """Read-side projection of one user row in the popularity ranking.

    The ranking covers **every** registered, non-banned user — a user
    who has never published a course still appears (at the tail) with
    zeroed metrics, so the list doubles as a full user directory. The
    two metrics are computed in the same aggregate query that produces
    the row:

    - ``student_count`` — number of **distinct** students with an
      ``ACTIVE`` enrollment across the user's published products. A
      student enrolled in two of the same teacher's courses counts
      once; ``REVOKED`` enrollments are excluded. ``0`` for a user with
      no students.
    - ``published_product_count`` — number of the user's ``PUBLISHED``
      products (``0`` for a user with none). Used as the secondary
      ranking key so two users with the same student count are ordered
      by catalog breadth.

    Name parts mirror :class:`UserSummaryView`; the avatar is resolved
    to a :class:`FileMeta` so the caller can mint a thumbnail URL
    without a follow-up round-trip. ``email`` / ``description`` are
    deliberately absent — this is a public discovery projection.
    """

    oid: UserID
    first_name: str
    last_name: str
    patronymic: str | None
    is_verified: bool
    avatar: FileMeta | None
    student_count: int
    published_product_count: int


class TeacherRankingReader(Protocol):
    """Read-side source of the top-teachers popularity ranking."""

    async def top_by_students(
        self,
        pagination: Pagination,
    ) -> list[TopTeacherView]:
        """Return users ranked by their distinct active-student count.

        Every registered user is considered; only banned users are
        excluded. Ordering is ``student_count`` desc, then
        ``published_product_count`` desc, then ``last_name`` /
        ``first_name`` / ``oid`` ascending for a stable, deterministic
        page across requests. Users with zero students still appear (at
        the tail) so the ranking doubles as a full user directory.
        """
        ...
