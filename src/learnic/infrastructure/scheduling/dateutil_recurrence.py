from datetime import date, datetime, time

from dateutil.rrule import rrulestr
from typing_extensions import override

from learnic.application.common.scheduling.recurrence import (
    RecurrenceRuleValidator,
)
from learnic.entities.cohort.errors import InvalidRecurrenceRuleError
from learnic.entities.cohort.value_objects import RecurrenceRule


class DateutilRecurrenceRuleValidator(RecurrenceRuleValidator):
    """``RecurrenceRuleValidator`` backed by ``dateutil.rrule.rrulestr``.

    Format-level checks (length, ``FREQ=``, allowed characters) are
    handled by the VO itself; this adapter just confirms that
    ``rrulestr`` accepts the rule when anchored at ``starts_on``.
    Anything that ``rrulestr`` raises (``ValueError``,
    ``TypeError``) is re-thrown as
    :class:`InvalidRecurrenceRuleError` with ``reason="semantic"``.
    """

    @override
    def validate(self, rule: RecurrenceRule, starts_on: date) -> None:
        try:
            rrulestr(
                rule.value,
                dtstart=datetime.combine(starts_on, time.min),
            )
        except (ValueError, TypeError) as exc:
            raise InvalidRecurrenceRuleError("semantic") from exc
