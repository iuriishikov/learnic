import re
import zoneinfo

from learnic.entities.common.value_object import ValueObject
from learnic.entities.cohort.constants import (
    CANCELLATION_REASON_MAX_LEN,
    COHORT_NAME_MAX_LEN,
    IANA_TIMEZONE_MAX_LEN,
    RECORDING_URL_MAX_LEN,
    RRULE_MAX_LEN,
)
from learnic.entities.cohort.errors import (
    CohortFieldTooLongError,
    EmptyCohortFieldError,
    InvalidIanaTimezoneError,
    InvalidRecordingUrlError,
    InvalidRecurrenceRuleError,
)

_RRULE_PART_RE = re.compile(r"^[A-Z][A-Z0-9_]*=[A-Z0-9_,:+\-]+$")


class CohortName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyCohortFieldError("name")
        if len(self.value) > COHORT_NAME_MAX_LEN:
            raise CohortFieldTooLongError("name", COHORT_NAME_MAX_LEN)


class IanaTimezone(ValueObject):
    """An IANA timezone name (e.g. ``Europe/Sofia``).

    Validated against ``zoneinfo.ZoneInfo`` (stdlib), which raises
    ``ZoneInfoNotFoundError`` for any unknown name.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidIanaTimezoneError("empty")
        if len(self.value) > IANA_TIMEZONE_MAX_LEN:
            raise InvalidIanaTimezoneError("too_long")
        try:
            zoneinfo.ZoneInfo(self.value)
        except zoneinfo.ZoneInfoNotFoundError as exc:
            raise InvalidIanaTimezoneError("not_found") from exc


class RecurrenceRule(ValueObject):
    """An RFC 5545 RRULE string (e.g. ``FREQ=WEEKLY;BYDAY=FR``).

    Format-level guard only: checks length, presence of ``FREQ=``,
    and that each ``KEY=VALUE`` part matches an allowed character
    set. Semantic validity (whether the rule actually expands to a
    valid sequence of dates) is verified upstream by an
    ``application`` Protocol — keeping ``entities/`` stdlib-only.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidRecurrenceRuleError("empty")
        if len(self.value) > RRULE_MAX_LEN:
            raise InvalidRecurrenceRuleError("too_long")
        parts = self.value.split(";")
        if not any(part.startswith("FREQ=") for part in parts):
            raise InvalidRecurrenceRuleError("missing_freq")
        for part in parts:
            if not _RRULE_PART_RE.match(part):
                raise InvalidRecurrenceRuleError("invalid_part")


class CancellationReason(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyCohortFieldError("cancellation_reason")
        if len(self.value) > CANCELLATION_REASON_MAX_LEN:
            raise CohortFieldTooLongError(
                "cancellation_reason",
                CANCELLATION_REASON_MAX_LEN,
            )


class RecordingUrl(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidRecordingUrlError("empty")
        if len(self.value) > RECORDING_URL_MAX_LEN:
            raise InvalidRecordingUrlError("too_long")
        if not (self.value.startswith("https://") or self.value.startswith("http://")):
            raise InvalidRecordingUrlError("invalid_scheme")
