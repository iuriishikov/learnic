from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ContentEventKind,
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
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import HtmlBlock
from learnic.entities.course_block.value_objects import HtmlContent
from learnic.entities.role.permissions import Permission
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
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, HtmlBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.HTML.value,
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

        sanitized = self._html_sanitizer.sanitize(data.html)
        block.update_html(HtmlContent(sanitized))
        await self._block_gateway.update_html(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            kind=ContentEventKind.BLOCK_UPDATED,
            product_id=block.product_id,
            actor_id=data.actor_id,
            payload={
                "block_id": str(block.oid),
                "type": BlockType.HTML.value,
            },
        )
