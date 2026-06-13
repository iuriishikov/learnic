from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block._append import (
    commit_and_publish_added,
    prepare_block_append,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.collaboration import (
    ContentEventBus,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import TextInputBlock
from learnic.entities.note_block.value_objects import AcceptedAnswer
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddTextInputBlockCommand:
    """Append a new free-text answer block to a lesson.

    The author submits an ordered tuple of raw accepted-answer
    strings plus the two normalisation flags. The VOs (and the
    block entity) enforce all per-value and cross-value
    invariants — including uniqueness under the active
    normalisation, so toggling the flags can't silently create
    phantom duplicates.
    """

    actor_id: UserID
    lesson_id: NoteLessonID
    accepted_answers: tuple[str, ...]
    case_sensitive: bool
    trim_whitespace: bool


@final
class AddTextInputBlockCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        block_gateway: LessonBlockGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddTextInputBlockCommand) -> LessonBlockID:
        lesson, next_position = await prepare_block_append(
            actor_id=data.actor_id,
            lesson_id=data.lesson_id,
            authorizer=self._authorizer,
            product_gateway=self._product_gateway,
            lesson_gateway=self._lesson_gateway,
            block_gateway=self._block_gateway,
        )

        block = TextInputBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            accepted_answers=[AcceptedAnswer(a) for a in data.accepted_answers],
            case_sensitive=data.case_sensitive,
            trim_whitespace=data.trim_whitespace,
            position=next_position,
        )
        await self._block_gateway.add_text_input(block)
        await commit_and_publish_added(
            transaction=self._transaction,
            event_bus=self._event_bus,
            lesson_id=data.lesson_id,
            block=block,
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
        return block.oid
