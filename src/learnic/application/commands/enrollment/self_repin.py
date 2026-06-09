from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SelfRePinNoteEnrollmentCommand:
    actor_id: UserID
    enrollment_id: EnrollmentID
    release_id: NoteReleaseID


@final
class SelfRePinNoteEnrollmentCommandHandler:
    """Let an enrolled student move their OWN enrollment's pinned release.

    The student-facing counterpart of
    :class:`RePinNoteEnrollmentCommandHandler`. The author version
    authorises on ``MANAGE_RELEASES``; this one is caller-scoped — the
    actor must be the enrollment's own student, so no product permission
    is required and there is no authorizer dependency. A mismatched or
    missing enrollment is reported as ``EntityNotFound`` (the caller has
    no business knowing it exists), not a 403.

    The target release must belong to the same note as the enrollment,
    and only ACTIVE enrollments may be re-pinned — the entity raises
    :class:`CannotRepinRevokedEnrollmentError` otherwise. Strict pinning
    still holds: this is the explicit, opt-in way a student switches the
    version of the material they study (e.g. upgrade to the latest
    release, or step back to an older one).
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: EnrollmentGateway,
        release_gateway: NoteReleaseGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_gateway: Final = release_gateway

    async def run(self, data: SelfRePinNoteEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None or enrollment.student_id != data.actor_id:
            raise EntityNotFoundError(data.enrollment_id)
        release = await self._release_gateway.with_id(data.release_id)
        if release is None or release.product_id != enrollment.product_id:
            raise EntityNotFoundError(data.release_id)
        enrollment.repin_to_release(release.oid)
        await self._enrollment_gateway.update_note_details(enrollment)
        await self._transaction.commit()
