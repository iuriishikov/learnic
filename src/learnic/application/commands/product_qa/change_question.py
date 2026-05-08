from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_qa import (
    ProductQAGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.entities.product.ids import ProductQAID
from learnic.entities.product.value_objects import QAQuestion
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductQAQuestionCommand:
    actor_id: UserID
    qa_id: ProductQAID
    value: str


@final
class ChangeProductQAQuestionCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        qa_gateway: ProductQAGateway,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._qa_gateway: Final = qa_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: ChangeProductQAQuestionCommand) -> None:
        qa = await self._qa_gateway.with_id(data.qa_id)
        if qa is None:
            raise EntityNotFoundError(data.qa_id)
        product = await self._product_gateway.with_id(qa.product_id)
        if product is None:
            raise EntityNotFoundError(qa.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(qa.product_id),
            Permission.EDIT_QA,
        )
        new_question = QAQuestion(data.value)
        qa.change_question(new_question)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.QA_QUESTION_CHANGED,
            product_id=qa.product_id,
            actor_id=data.actor_id,
            payload={
                "qa_id": str(qa.oid),
                "question": new_question.value,
            },
        )
