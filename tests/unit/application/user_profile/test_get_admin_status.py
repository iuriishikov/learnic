import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.queries.user.get_admin_status import (
    GetMyAdminStatusQuery,
    GetMyAdminStatusQueryHandler,
)
from learnic.entities.user.models import UserID


@pytest.mark.parametrize("flag", [True, False])
async def test_returns_reader_flag(flag: bool) -> None:
    user_id = UserID(uuid.uuid4())
    reader = AsyncMock()
    reader.is_admin = AsyncMock(return_value=flag)

    handler = GetMyAdminStatusQueryHandler(user_reader=reader)
    result = await handler.run(GetMyAdminStatusQuery(user_id=user_id))

    assert result.is_admin is flag
    reader.is_admin.assert_awaited_once_with(user_id)


async def test_missing_user_raises_not_found() -> None:
    user_id = UserID(uuid.uuid4())
    reader = AsyncMock()
    reader.is_admin = AsyncMock(return_value=None)

    handler = GetMyAdminStatusQueryHandler(user_reader=reader)
    with pytest.raises(EntityNotFoundError):
        await handler.run(GetMyAdminStatusQuery(user_id=user_id))
