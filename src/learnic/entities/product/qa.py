import uuid
from dataclasses import dataclass
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID, ProductQAID
from learnic.entities.product.value_objects import QAAnswer, QAQuestion


@dataclass
class ProductQA(BaseEntity[ProductQAID]):
    """A single Q&A entry attached to a :class:`Product`.

    Lives inside the Product aggregate (CASCADE on parent delete),
    but has its own Gateway/Reader so individual entries can be
    edited without loading the whole product.
    """

    product_id: ProductID
    question: QAQuestion
    answer: QAAnswer
    position: int

    def change_question(self, new_question: QAQuestion) -> None:
        self.question = new_question

    def change_answer(self, new_answer: QAAnswer) -> None:
        self.answer = new_answer

    def reposition(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        product_id: ProductID,
        question: QAQuestion,
        answer: QAAnswer,
        position: int,
    ) -> Self:
        return cls(
            oid=ProductQAID(uuid.uuid4()),
            product_id=product_id,
            question=question,
            answer=answer,
            position=position,
        )
