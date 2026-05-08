import zoneinfo
from datetime import date, datetime, time, timezone

from dateutil.rrule import rrulestr
from typing_extensions import override

from learnic.application.common.scheduling.materializer import (
    ScheduleMaterializer,
)
from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)


class DateutilScheduleMaterializer(ScheduleMaterializer):
    """``ScheduleMaterializer`` backed by ``dateutil.rrule``.

    Anchors the rule at midnight of ``starts_on`` in the schedule's
    local timezone — ``BYHOUR`` / ``BYMINUTE`` clauses then choose
    the actual time of day. Without a timezone-aware ``dtstart``
    ``dateutil`` produces naive datetimes that cannot be safely
    converted to UTC. ``ends_on`` is treated inclusively (end of the
    local day).
    """

    @override
    def materialize(
        self,
        rule: RecurrenceRule,
        tz: IanaTimezone,
        starts_on: date,
        ends_on: date | None,
        after: datetime | None,
        limit: int,
    ) -> list[datetime]:
        zone = zoneinfo.ZoneInfo(tz.value)
        local_dtstart = datetime.combine(starts_on, time.min, tzinfo=zone)
        until: datetime | None = (
            datetime.combine(ends_on, time.max, tzinfo=zone)
            if ends_on is not None
            else None
        )
        rule_set = rrulestr(rule.value, dtstart=local_dtstart)

        result: list[datetime] = []
        for occ in rule_set:
            if until is not None and occ > until:
                break
            utc_occ = occ.astimezone(timezone.utc)
            if after is not None and utc_occ <= after:
                continue
            result.append(utc_occ)
            if len(result) >= limit:
                break
        return result
