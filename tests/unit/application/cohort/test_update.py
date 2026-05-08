from datetime import date
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.cohort.reschedule import (
    RescheduleCohortCommand,
    RescheduleCohortCommandHandler,
)
from learnic.application.commands.cohort.update_max_participants import (
    UpdateCohortMaxParticipantsCommand,
    UpdateCohortMaxParticipantsCommandHandler,
)
from learnic.application.commands.cohort.update_name import (
    UpdateCohortNameCommand,
    UpdateCohortNameCommandHandler,
)
from learnic.application.common.errors import NotResourceOwnerError
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


async def test_update_name_by_host_succeeds(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = UpdateCohortNameCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        UpdateCohortNameCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            value="Renamed",
        ),
    )

    assert cohort.name is not None
    assert cohort.name.value == "Renamed"
    # Host check is the cheap path — product_gateway not consulted.
    fake_product_gateway.with_id.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_update_name_by_author_succeeds(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UpdateCohortNameCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        UpdateCohortNameCommand(
            actor_id=author_id,
            cohort_id=cohort.oid,
            value="By author",
        ),
    )

    assert cohort.name is not None
    assert cohort.name.value == "By author"
    fake_product_gateway.with_id.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_update_name_by_stranger_raises(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    webinar_product: Product,
    stranger_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UpdateCohortNameCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            UpdateCohortNameCommand(
                actor_id=stranger_id,
                cohort_id=cohort.oid,
                value="Hacked",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_update_name_with_none_clears(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = UpdateCohortNameCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        UpdateCohortNameCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            value=None,
        ),
    )

    assert cohort.name is None


async def test_update_max_participants_clears(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = UpdateCohortMaxParticipantsCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        UpdateCohortMaxParticipantsCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            value=None,
        ),
    )

    assert cohort.max_participants is None


async def test_reschedule_updates_dates(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = RescheduleCohortCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    new_start = date(2026, 10, 1)
    new_end = date(2027, 1, 1)
    await handler.run(
        RescheduleCohortCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            starts_on=new_start,
            ends_on=new_end,
        ),
    )

    assert cohort.starts_on == new_start
    assert cohort.ends_on == new_end
