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
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import RutubeVideoBlock
from learnic.entities.note_block.value_objects import (
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateRutubeVideoBlockCommand:
    """Replace the Rutube URL and/or the title of an existing video block.

    ``rutube_url`` is required (the video reference is the load-bearing
    field). ``title`` may be ``None`` to clear an existing caption,
    or a string to set/update it.
    """

    actor_id: UserID
    block_id: LessonBlockID
    rutube_url: str
    title: str | None


@final
class UpdateRutubeVideoBlockCommandHandler:
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

    async def run(self, data: UpdateRutubeVideoBlockCommand) -> None:
        block = await load_typed_block_for_edit(
            block_id=data.block_id,
            actor_id=data.actor_id,
            expected_type=BlockType.RUTUBE_VIDEO,
            expected_cls=RutubeVideoBlock,
            block_gateway=self._block_gateway,
            product_gateway=self._product_gateway,
            authorizer=self._authorizer,
        )

        block.update_external_id(RutubeVideoID.from_url(data.rutube_url))
        block.update_title(
            VideoTitle(data.title) if data.title is not None else None,
        )
        await self._block_gateway.update_rutube_video(block)
        await commit_and_publish_updated(
            transaction=self._transaction,
            event_bus=self._event_bus,
            block=block,
            actor_id=data.actor_id,
        )
