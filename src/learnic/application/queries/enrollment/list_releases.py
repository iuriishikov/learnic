from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseReader,
    NoteReleaseSummaryView,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListEnrollmentReleasesQuery:
    actor_id: UserID
    enrollment_id: EnrollmentID


@final
class ListEnrollmentReleasesQueryHandler:
    """List the releases a student can switch their own enrollment to.

    Caller-scoped sibling of
    :class:`ListNoteReleasesQueryHandler` (which gates on
    ``READ_PRODUCT`` and is author/collaborator-only). Here the actor
    must own the enrollment; a missing or someone-else's enrollment is
    reported as ``EntityNotFound``. Returns the same
    :class:`NoteReleaseSummaryView` list (newest first) as the
    author-side endpoint, so an enrolled student sees every release they
    could self-re-pin to.

    Mirrors the gateway-for-existence + reader-for-view split used by
    :class:`ListNoteReleasesQueryHandler`.
    """

    def __init__(
        self,
        enrollment_gateway: EnrollmentGateway,
        release_reader: NoteReleaseReader,
    ) -> None:
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: ListEnrollmentReleasesQuery,
    ) -> list[NoteReleaseSummaryView]:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None or enrollment.student_id != data.actor_id:
            raise EntityNotFoundError(data.enrollment_id)
        return await self._release_reader.list_for_product(
            enrollment.product_id,
        )
