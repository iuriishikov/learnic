from dataclasses import dataclass
from typing import Final, final

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
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import HtmlBlock
from learnic.entities.note_block.value_objects import HtmlContent
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateHtmlBlockCommand:
    actor_id: UserID
    block_id: LessonBlockID
    html: str


@final
class UpdateHtmlBlockCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        html_sanitizer: HtmlSanitizer,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._html_sanitizer: Final = html_sanitizer
        self._event_bus: Final = event_bus

    async def run(self, data: UpdateHtmlBlockCommand) -> None:
        block = await load_typed_block_for_edit(
            block_id=data.block_id,
            actor_id=data.actor_id,
            expected_type=BlockType.HTML,
            expected_cls=HtmlBlock,
            block_gateway=self._block_gateway,
            product_gateway=self._product_gateway,
            authorizer=self._authorizer,
        )

        sanitized = await self._html_sanitizer.sanitize(data.html)
        block.update_html(HtmlContent(sanitized))
        await self._block_gateway.update_html(block)
        await commit_and_publish_updated(
            transaction=self._transaction,
            event_bus=self._event_bus,
            block=block,
            actor_id=data.actor_id,
        )
