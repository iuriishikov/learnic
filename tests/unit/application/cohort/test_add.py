from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.cohort.add import (
    AddCohortCommand,
    AddCohortCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    NotAWebinarError,
)
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.models import Product
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


def _allow_authorizer() -> AsyncMock:
    authorizer = AsyncMock()
    authorizer.require = AsyncMock(return_value=None)
    return authorizer


def _deny_authorizer(actor_id: UserID, product_id: object) -> AsyncMock:
    authorizer = AsyncMock()
    authorizer.require = AsyncMock(
        side_effect=InsufficientPermissionsError(
            user_id=actor_id,
            product_id=product_id,
            permission=Permission.MANAGE_RELEASES.value,
        ),
    )
    return authorizer


async def test_add_cohort_persists_and_returns_id(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
    host_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = AddCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        authorizer=_allow_authorizer(),
    )

    cohort_id = await handler.run(
        AddCohortCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
            host_id=host_id,
            starts_on=date(2026, 9, 1),
            name="Поток №3",
            max_participants=30,
            ends_on=date(2026, 12, 15),
        ),
    )

    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, Cohort)
    assert saved.oid == cohort_id
    assert saved.webinar_id == webinar_product.oid
    assert saved.host_id == host_id
    fake_transaction.commit.assert_awaited_once()


async def test_add_cohort_without_permission_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    webinar_product: Product,
    stranger_id: UserID,
    host_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = AddCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        authorizer=_deny_authorizer(stranger_id, webinar_product.oid),
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddCohortCommand(
                actor_id=stranger_id,
                product_id=webinar_product.oid,
                host_id=host_id,
                starts_on=date(2026, 9, 1),
                name=None,
                max_participants=None,
                ends_on=None,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_add_cohort_on_course_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    course_product: Product,
    author_id: UserID,
    host_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = AddCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        authorizer=_allow_authorizer(),
    )

    with pytest.raises(NotAWebinarError):
        await handler.run(
            AddCohortCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                host_id=host_id,
                starts_on=date(2026, 9, 1),
                name=None,
                max_participants=None,
                ends_on=None,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()


async def test_add_cohort_missing_product_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
    host_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = None
    handler = AddCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        authorizer=_allow_authorizer(),
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AddCohortCommand(
                actor_id=author_id,
                product_id=webinar_product.oid,
                host_id=host_id,
                starts_on=date(2026, 9, 1),
                name=None,
                max_participants=None,
                ends_on=None,
            ),
        )
