from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block.add_code import (
    CodeTabInput,
    _to_domain_tabs,
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
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import CodeBlock
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateCodeBlockCommand:
    """Replace the entire tabs list of an existing code block.

    Per-tab partial updates were considered and rejected: with
    optimistic concurrency a partial PATCH (e.g. "rename tab 2")
    would race against a concurrent reorder/insert. Replacing the
    whole list is unambiguous — the client always sends the full
    desired state, the server validates invariants once.
    """

    actor_id: UserID
    block_id: LessonBlockID
    tabs: tuple[CodeTabInput, ...]


@final
class UpdateCodeBlockCommandHandler:
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

    async def run(self, data: UpdateCodeBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, CodeBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.CODE.value,
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

        block.replace_tabs(_to_domain_tabs(data.tabs))
        await self._block_gateway.update_code(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
