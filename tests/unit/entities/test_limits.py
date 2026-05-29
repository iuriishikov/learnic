import pytest

from learnic.entities.common.limits import (
    LESSON_BLOCK_LIMIT,
    PRODUCT_LIMIT,
    USER_EXPERIENCE_LIMIT,
    LimitedResource,
    ResourceLimit,
    ResourceLimitReachedError,
)


def test_ensure_under_limit_is_silent() -> None:
    limit = ResourceLimit(LimitedResource.LESSON_BLOCK, 3)
    limit.ensure(0)
    limit.ensure(2)


@pytest.mark.parametrize("current", [3, 4, 100])
def test_ensure_at_or_over_limit_raises(current: int) -> None:
    limit = ResourceLimit(LimitedResource.PRODUCT, 3)
    with pytest.raises(ResourceLimitReachedError) as exc_info:
        limit.ensure(current)
    assert exc_info.value.resource is LimitedResource.PRODUCT
    assert exc_info.value.limit == 3


def test_registry_entries_are_resource_limits() -> None:
    assert isinstance(LESSON_BLOCK_LIMIT, ResourceLimit)
    assert isinstance(PRODUCT_LIMIT, ResourceLimit)
    assert isinstance(USER_EXPERIENCE_LIMIT, ResourceLimit)
    assert LESSON_BLOCK_LIMIT.resource is LimitedResource.LESSON_BLOCK
    assert USER_EXPERIENCE_LIMIT.resource is LimitedResource.USER_EXPERIENCE
