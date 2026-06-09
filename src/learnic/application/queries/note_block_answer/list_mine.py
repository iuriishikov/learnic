"""List the current student's saved answers for a note.

Backs the SPA's "restore my progress" call: returns the learner's
persisted submissions for the release they are pinned to, so the
reader can pre-fill selections + verdicts. Mirrors the release
resolution in :class:`GetNoteContentQueryHandler` (active enrollment →
pinned release) so the answers always line up with the content the
student is actually viewing.

Not an error path: a caller who is signed in but not actively enrolled
(or whose product is not a note) simply has no saved answers, so the
handler returns an empty list rather than raising. The HTTP layer
still requires a valid access cookie.
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_block_answer import (
    NoteBlockAnswerReader,
    NoteBlockAnswerView,
)
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListMyBlockAnswersQuery:
    actor_id: UserID
    product_id: ProductID


@final
class ListMyBlockAnswersQueryHandler:
    def __init__(
        self,
        enrollment_gateway: EnrollmentGateway,
        answer_reader: NoteBlockAnswerReader,
    ) -> None:
        self._enrollment_gateway: Final = enrollment_gateway
        self._answer_reader: Final = answer_reader

    async def run(
        self,
        data: ListMyBlockAnswersQuery,
    ) -> list[NoteBlockAnswerView]:
        enrollment = await self._enrollment_gateway.with_product_and_student(
            data.product_id,
            data.actor_id,
        )
        if (
            enrollment is None
            or enrollment.status is not EnrollmentStatus.ACTIVE
            or not isinstance(enrollment.details, NoteEnrollmentDetails)
        ):
            # Not an actively-enrolled note student → no saved answers.
            return []
        return await self._answer_reader.for_release(
            data.actor_id,
            enrollment.details.release_id,
        )
