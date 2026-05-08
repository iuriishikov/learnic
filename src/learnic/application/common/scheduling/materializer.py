from datetime import date, datetime
from typing import Protocol

from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)


class ScheduleMaterializer(Protocol):
    """Expands a recurrence rule into concrete UTC datetimes.

    Used by the ``materialize_webinar_schedule`` background task to
    create :class:`WebinarSession` rows from a
    :class:`WebinarSchedule`. Sessions are stored as timezone-aware
    UTC datetimes; the ``tz`` argument tells the materializer how to
    interpret the schedule's local clock before converting.

    The implementation must guard against unbounded expansion of
    open-ended rules (``FREQ=DAILY`` without ``COUNT`` / ``UNTIL``)
    by honoring the ``limit`` argument.
    """

    def materialize(
        self,
        rule: RecurrenceRule,
        tz: IanaTimezone,
        starts_on: date,
        ends_on: date | None,
        after: datetime | None,
        limit: int,
    ) -> list[datetime]:
        """Return up to ``limit`` UTC datetimes for the rule.

        Args:
            rule: The recurrence rule.
            tz: Local timezone the rule is anchored to (e.g.
                ``Europe/Sofia``); output is converted to UTC.
            starts_on: First permissible date (inclusive); used as
                ``DTSTART``.
            ends_on: Last permissible date (inclusive); ``None``
                for open-ended rules — bounded only by ``limit``.
            after: If supplied, return only datetimes strictly later
                than this (UTC) — lets the worker pick up where it
                left off without regenerating prior sessions.
            limit: Maximum number of datetimes to return.

        Returns:
            UTC, timezone-aware datetimes in ascending order.
        """
        ...
