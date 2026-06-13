from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block._typed_update import (
    commit_and_publish_updated,
    load_typed_block_for_edit,
)
from learnic.application.commands.note_block.add_code import (
    CodeTabInput,
    _to_domain_tabs,
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
from learnic.entities.note_block.models import CodeBlock
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
        block = await load_typed_block_for_edit(
            block_id=data.block_id,
            actor_id=data.actor_id,
            expected_type=BlockType.CODE,
            expected_cls=CodeBlock,
            block_gateway=self._block_gateway,
            product_gateway=self._product_gateway,
            authorizer=self._authorizer,
        )

        block.replace_tabs(_to_domain_tabs(data.tabs))
        await self._block_gateway.update_code(block)
        await commit_and_publish_updated(
            transaction=self._transaction,
            event_bus=self._event_bus,
            block=block,
            actor_id=data.actor_id,
        )
