from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RePinNoteEnrollmentCommand:
    actor_id: UserID
    enrollment_id: EnrollmentID
    release_id: NoteReleaseID


@final
class RePinNoteEnrollmentCommandHandler:
    """Move a note enrollment's pinned release.

    Caller needs ``MANAGE_RELEASES`` on the parent product (owner
    short-circuits inside the authorizer). The target release
    must belong to the same product as the enrollment — releases
    of unrelated notes are not legal pins.

    Strict pinning is the default policy: students never
    auto-upgrade. This endpoint is the explicit escape hatch for
    authors to move a student to a different release (e.g. push
    a hotfix to a single cohort, or pull a student back to an
    earlier version of the material).
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: EnrollmentGateway,
        release_gateway: NoteReleaseGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_gateway: Final = release_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: RePinNoteEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(enrollment.product_id),
            Permission.MANAGE_RELEASES,
        )
        release = await self._release_gateway.with_id(data.release_id)
        if release is None or release.product_id != enrollment.product_id:
            raise EntityNotFoundError(data.release_id)
        enrollment.repin_to_release(release.oid)
        await self._enrollment_gateway.update_note_details(enrollment)
        await self._transaction.commit()
