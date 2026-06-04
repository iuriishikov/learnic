from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ModuleAddedPayload,
    publish_content_event,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.common.limits import NOTE_MODULE_LIMIT
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_module.models import NoteModule
from learnic.entities.note_module.value_objects import (
    ModuleDescription,
    ModuleTitle,
)
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddNoteModuleCommand:
    actor_id: UserID
    product_id: ProductID
    title: str
    description: str | None = None


@final
class AddNoteModuleCommandHandler:
    """Append a new module to a note product's draft."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        module_gateway: NoteModuleGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddNoteModuleCommand) -> NoteModuleID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_MODULES,
        )
        product.require_supports(ProductCapability.HAS_NOTE_CONTENT)

        await self._module_gateway.lock_for_product(data.product_id)
        existing = await self._module_gateway.for_product(data.product_id)
        NOTE_MODULE_LIMIT.ensure(len(existing))
        next_position = max((m.position for m in existing), default=-1) + 1

        description = (
            ModuleDescription(data.description)
            if data.description is not None
            else None
        )
        module = NoteModule.create(
            product_id=data.product_id,
            title=ModuleTitle(data.title),
            position=next_position,
            description=description,
        )
        self._entity_saver.add_one(module)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=ModuleAddedPayload.from_entity(module),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        return module.oid
