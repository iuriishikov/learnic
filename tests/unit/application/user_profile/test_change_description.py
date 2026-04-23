from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.user.change_description import (
    ChangeUserDescriptionCommand,
    ChangeUserDescriptionCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.user.errors import InvalidDescriptionError
from learnic.entities.user.value_objects import UserDescription


async def test_change_description_sanitizes_then_wraps_in_vo(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user
    fake_html_sanitizer.sanitize.side_effect = lambda raw: raw.replace(
        "<script>bad</script>", ""
    )

    handler = ChangeUserDescriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        html_sanitizer=fake_html_sanitizer,
    )
    await handler.run(
        ChangeUserDescriptionCommand(
            user_id=user.oid,
            html="<p>hi</p><script>bad</script>",
        )
    )

    fake_html_sanitizer.sanitize.assert_called_once_with(
        "<p>hi</p><script>bad</script>"
    )
    assert user.description == UserDescription("<p>hi</p>")
    fake_transaction.commit.assert_awaited_once()


async def test_change_description_null_clears(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    user,
) -> None:
    user.description = UserDescription("<p>old</p>")
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserDescriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        html_sanitizer=fake_html_sanitizer,
    )
    await handler.run(ChangeUserDescriptionCommand(user_id=user.oid, html=None))

    assert user.description is None
    fake_html_sanitizer.sanitize.assert_not_called()
    fake_transaction.commit.assert_awaited_once()


async def test_change_description_user_missing_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = ChangeUserDescriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        html_sanitizer=fake_html_sanitizer,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ChangeUserDescriptionCommand(user_id=user.oid, html="<p>x</p>")
        )
    fake_transaction.commit.assert_not_called()


async def test_change_description_empty_after_sanitize_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user
    fake_html_sanitizer.sanitize.side_effect = lambda _: ""

    handler = ChangeUserDescriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        html_sanitizer=fake_html_sanitizer,
    )
    with pytest.raises(InvalidDescriptionError):
        await handler.run(
            ChangeUserDescriptionCommand(user_id=user.oid, html="<script>bad</script>")
        )
    fake_transaction.commit.assert_not_called()
