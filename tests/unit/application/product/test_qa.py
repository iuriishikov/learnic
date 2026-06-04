from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.product_qa.add import (
    AddProductQACommand,
    AddProductQACommandHandler,
)
from learnic.application.commands.product_qa.change_question import (
    ChangeProductQAQuestionCommand,
    ChangeProductQAQuestionCommandHandler,
)
from learnic.application.commands.product_qa.delete import (
    DeleteProductQACommand,
    DeleteProductQACommandHandler,
)
from learnic.application.commands.product_qa.reorder import (
    ReorderProductQACommand,
    ReorderProductQACommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.application.common.product_events import (
    QaDeletedPayload,
    QaQuestionChangedPayload,
    QaReorderedPayload,
)
from learnic.entities.product.models import Product
from learnic.entities.product.qa import ProductQA
from learnic.entities.product.value_objects import QAAnswer, QAQuestion
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_qa_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    gateway.delete = AsyncMock()
    gateway.count_for_product = AsyncMock(return_value=0)
    return gateway


@pytest.fixture
def existing_qa(note_product: Product) -> ProductQA:
    return ProductQA.create(
        product_id=note_product.oid,
        question=QAQuestion("Old question?"),
        answer=QAAnswer("Old answer."),
        position=0,
    )


async def test_add_qa_persists_and_returns_id(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    handler = AddProductQACommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    qa_id = await handler.run(
        AddProductQACommand(
            actor_id=author_id,
            product_id=note_product.oid,
            question="Will I get a certificate?",
            answer="Yes.",
            position=0,
        ),
    )

    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, ProductQA)
    assert saved.oid == qa_id
    assert saved.product_id == note_product.oid
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "qa_added"
    assert event.product_id == note_product.oid
    assert event.payload.qa_id == str(qa_id)
    assert event.payload.question == "Will I get a certificate?"
    assert event.payload.answer == "Yes."
    assert event.payload.position == 0


async def test_add_qa_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_qa",
    )
    handler = AddProductQACommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddProductQACommand(
                actor_id=other_user_id,
                product_id=note_product.oid,
                question="?",
                answer="!",
                position=0,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_change_question_updates_value(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    existing_qa: ProductQA,
    author_id: UserID,
) -> None:
    fake_qa_gateway.with_id.return_value = existing_qa
    fake_product_gateway.with_id.return_value = note_product
    handler = ChangeProductQAQuestionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ChangeProductQAQuestionCommand(
            actor_id=author_id,
            qa_id=existing_qa.oid,
            value="New question?",
        ),
    )

    assert existing_qa.question.value == "New question?"
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "qa_question_changed"
    assert event.payload == QaQuestionChangedPayload(
        qa_id=str(existing_qa.oid),
        question="New question?",
    )


async def test_change_question_missing_qa_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    existing_qa: ProductQA,
    author_id: UserID,
) -> None:
    fake_qa_gateway.with_id.return_value = None
    handler = ChangeProductQAQuestionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ChangeProductQAQuestionCommand(
                actor_id=author_id,
                qa_id=existing_qa.oid,
                value="?",
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_change_question_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    existing_qa: ProductQA,
    other_user_id: UserID,
) -> None:
    fake_qa_gateway.with_id.return_value = existing_qa
    fake_product_gateway.with_id.return_value = note_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_qa",
    )
    handler = ChangeProductQAQuestionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            ChangeProductQAQuestionCommand(
                actor_id=other_user_id,
                qa_id=existing_qa.oid,
                value="hijack",
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_reorder_updates_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    existing_qa: ProductQA,
    author_id: UserID,
) -> None:
    fake_qa_gateway.with_id.return_value = existing_qa
    fake_product_gateway.with_id.return_value = note_product
    handler = ReorderProductQACommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ReorderProductQACommand(
            actor_id=author_id,
            qa_id=existing_qa.oid,
            position=5,
        ),
    )

    assert existing_qa.position == 5
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "qa_reordered"
    assert event.payload == QaReorderedPayload(
        qa_id=str(existing_qa.oid), position=5,
    )


async def test_delete_qa_calls_gateway_delete(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_qa_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    existing_qa: ProductQA,
    author_id: UserID,
) -> None:
    fake_qa_gateway.with_id.return_value = existing_qa
    fake_product_gateway.with_id.return_value = note_product
    handler = DeleteProductQACommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        qa_gateway=fake_qa_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeleteProductQACommand(
            actor_id=author_id,
            qa_id=existing_qa.oid,
        ),
    )

    fake_qa_gateway.delete.assert_awaited_once_with(existing_qa)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "qa_deleted"
    assert event.payload == QaDeletedPayload(qa_id=str(existing_qa.oid))
