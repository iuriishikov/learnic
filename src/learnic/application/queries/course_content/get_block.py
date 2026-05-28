from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_content import (
    CourseContentReader,
    LessonBlockView,
)
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetLessonBlockQuery:
    actor_id: UserID
    block_id: LessonBlockID


@final
class GetLessonBlockQueryHandler:
    """Return the read-side projection of a single lesson block.

    Caller needs ``READ_PRODUCT`` on the block's owning product, so
    the owner and any collaborator with that permission can fetch
    the updated block after a mutation. Returning the full view from
    add/update endpoints lets the SPA ``setQueryData`` instead of
    re-invalidating the whole course-content tree.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        content_reader: CourseContentReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._content_reader: Final = content_reader

    async def run(self, data: GetLessonBlockQuery) -> LessonBlockView:
        result = await self._content_reader.with_block_id(data.block_id)
        if result is None:
            raise EntityNotFoundError(data.block_id)
        product_id, view = result
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(product_id),
            Permission.READ_PRODUCT,
        )
        return view
