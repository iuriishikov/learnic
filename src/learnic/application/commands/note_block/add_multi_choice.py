from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block._append import (
    commit_and_publish_added,
    prepare_block_append,
)
from learnic.application.commands.note_block._inputs import (
    ChoiceOptionDraftInput,
    options_with_multi_correct,
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
from learnic.entities.note_block.models import MultiChoiceBlock
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddMultiChoiceBlockCommand:
    """Append a new multi-choice answer block to a lesson.

    The author submits the option set with at least one
    ``is_correct=True`` entry. Order of correct options does not
    matter — the entity stores them as a frozenset.
    """

    actor_id: UserID
    lesson_id: NoteLessonID
    options: tuple[ChoiceOptionDraftInput, ...]


@final
class AddMultiChoiceBlockCommandHandler:
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

    async def run(self, data: AddMultiChoiceBlockCommand) -> LessonBlockID:
        lesson, next_position = await prepare_block_append(
            actor_id=data.actor_id,
            lesson_id=data.lesson_id,
            authorizer=self._authorizer,
            product_gateway=self._product_gateway,
            lesson_gateway=self._lesson_gateway,
            block_gateway=self._block_gateway,
        )

        options, correct_ids = options_with_multi_correct(data.options)
        block = MultiChoiceBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            options=options,
            correct_option_ids=correct_ids,
            position=next_position,
        )
        await self._block_gateway.add_multi_choice(block)
        await commit_and_publish_added(
            transaction=self._transaction,
            event_bus=self._event_bus,
            lesson_id=data.lesson_id,
            block=block,
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
        return block.oid
