from datetime import date
from typing import Protocol

from learnic.entities.cohort.value_objects import RecurrenceRule


class RecurrenceRuleValidator(Protocol):
    """Validates the *semantic* correctness of an RFC 5545 RRULE.

    The :class:`RecurrenceRule` value object already enforces
    format-level invariants (length, presence of ``FREQ=``, allowed
    character set per part). This Protocol catches everything else —
    invalid enum values (e.g. ``BYDAY=ZZ``), incompatible combinations,
    rules that don't expand to any datetime — by attempting to parse
    the rule via a real RFC 5545 implementation. Command handlers
    must call ``validate(...)`` before persisting a schedule.
    """

    def validate(self, rule: RecurrenceRule, starts_on: date) -> None:
        """Validate ``rule`` by attempting to parse it.

        Args:
            rule: The recurrence rule to validate.
            starts_on: The schedule's start date — used as
                ``DTSTART`` so that ``UNTIL=<naive>`` references
                resolve correctly.

        Raises:
            InvalidRecurrenceRuleError: ``reason="semantic"`` if the
                rule cannot be parsed by the underlying RFC 5545
                engine.
        """
        ...
