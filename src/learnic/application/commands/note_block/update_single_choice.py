from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block._inputs import (
    ChoiceOptionDraftInput,
    options_with_single_correct,
)
from learnic.application.commands.note_block._typed_update import (
    commit_and_publish_updated,
    load_typed_block_for_edit,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.collaboration import (
    ContentEventBus,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import SingleChoiceBlock
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateSingleChoiceBlockCommand:
    """Replace the option list and correct answer of an existing block.

    Replace semantics, like ``UpdateCodeBlockCommand``. Each update
    mints fresh option ids — there are no external references to
    option ids, so identity preservation across edits would add
    complexity without payoff.
    """

    actor_id: UserID
    block_id: LessonBlockID
    options: tuple[ChoiceOptionDraftInput, ...]


@final
class UpdateSingleChoiceBlockCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: UpdateSingleChoiceBlockCommand) -> None:
        block = await load_typed_block_for_edit(
            block_id=data.block_id,
            actor_id=data.actor_id,
            expected_type=BlockType.SINGLE_CHOICE,
            expected_cls=SingleChoiceBlock,
            block_gateway=self._block_gateway,
            product_gateway=self._product_gateway,
            authorizer=self._authorizer,
        )

        options, correct_id = options_with_single_correct(data.options)
        block.replace_options(options, correct_id)
        await self._block_gateway.update_single_choice(block)
        await commit_and_publish_updated(
            transaction=self._transaction,
            event_bus=self._event_bus,
            block=block,
            actor_id=data.actor_id,
        )
