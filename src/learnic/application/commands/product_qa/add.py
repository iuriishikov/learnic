from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_qa import (
    ProductQAGateway,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.product_events import (
    ProductEventBus,
    QaAddedPayload,
    publish_product_event,
)
from learnic.entities.common.limits import PRODUCT_QA_LIMIT
from learnic.entities.product.ids import ProductID, ProductQAID
from learnic.entities.product.qa import ProductQA
from learnic.entities.product.value_objects import QAAnswer, QAQuestion
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddProductQACommand:
    actor_id: UserID
    product_id: ProductID
    question: str
    answer: str
    position: int


@final
class AddProductQACommandHandler:
    """Adds a new Q&A entry to a product owned by ``actor_id``."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        qa_gateway: ProductQAGateway,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._qa_gateway: Final = qa_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddProductQACommand) -> ProductQAID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_QA,
        )
        PRODUCT_QA_LIMIT.ensure(
            await self._qa_gateway.count_for_product(data.product_id),
        )
        qa = ProductQA.create(
            product_id=data.product_id,
            question=QAQuestion(data.question),
            answer=QAAnswer(data.answer),
            position=data.position,
        )
        self._entity_saver.add_one(qa)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=QaAddedPayload(
                qa_id=str(qa.oid),
                question=qa.question.value,
                answer=qa.answer.value,
                position=qa.position,
            ),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        return qa.oid
