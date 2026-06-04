from dataclasses import dataclass
from datetime import datetime

from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.enrollment.value_objects import ProgressPercent


@dataclass
class EnrollmentDetails:
    """Polymorphic body for an :class:`Enrollment`.

    The base class is empty — each enrollment kind defines a
    concrete subclass with kind-specific fields. Same pattern as
    :class:`NotificationDetails`.
    """


@dataclass
class NoteEnrollmentDetails(EnrollmentDetails):
    """Note-kind specific data for an :class:`Enrollment`.

    Lives in the ``enrollment_note_details`` subtype table,
    loaded out-of-band by the gateway after the parent row.
    """

    release_id: NoteReleaseID
    progress: ProgressPercent
    completed_at: datetime | None = None
