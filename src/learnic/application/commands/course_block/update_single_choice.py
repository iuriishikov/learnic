from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.course_block._inputs import (
    ChoiceOptionDraftInput,
    options_with_single_correct,
)
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import SingleChoiceBlock
from learnic.entities.role.permissions import Permission
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
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, SingleChoiceBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.SINGLE_CHOICE.value,
                actual=block.type.value,
            )
        product = await self._product_gateway.with_id(block.product_id)
        if product is None:
            raise EntityNotFoundError(block.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(block.product_id),
            Permission.EDIT_LESSONS,
        )

        options, correct_id = options_with_single_correct(data.options)
        block.replace_options(options, correct_id)
        await self._block_gateway.update_single_choice(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
