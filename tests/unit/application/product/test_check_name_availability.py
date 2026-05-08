from unittest.mock import AsyncMock

from learnic.application.queries.product.check_name_availability import (
    CheckProductNameAvailabilityQuery,
    CheckProductNameAvailabilityQueryHandler,
)
from learnic.entities.user.models import UserID


async def test_returns_available_when_author_has_no_such_name(
    fake_product_reader: AsyncMock,
    author_id: UserID,
) -> None:
    fake_product_reader.name_exists.return_value = False
    handler = CheckProductNameAvailabilityQueryHandler(
        reader=fake_product_reader,
    )

    result = await handler.run(
        CheckProductNameAvailabilityQuery(
            author_id=author_id,
            name="Async Python",
        ),
    )

    assert result.available is True
    fake_product_reader.name_exists.assert_awaited_once_with(
        author_id,
        "Async Python",
    )


async def test_returns_unavailable_when_author_already_owns_name(
    fake_product_reader: AsyncMock,
    author_id: UserID,
) -> None:
    fake_product_reader.name_exists.return_value = True
    handler = CheckProductNameAvailabilityQueryHandler(
        reader=fake_product_reader,
    )

    result = await handler.run(
        CheckProductNameAvailabilityQuery(
            author_id=author_id,
            name="Taken",
        ),
    )

    assert result.available is False
    fake_product_reader.name_exists.assert_awaited_once_with(
        author_id,
        "Taken",
    )
