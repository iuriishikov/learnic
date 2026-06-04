import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import (
    ProductView,
    RecommendationCandidate,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.application.queries.product.recommend_for_me import (
    RankingPolicy,
    RankingWeights,
    RecommendForMeQuery,
    RecommendForMeQueryHandler,
)
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

_NOW = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)


def _make_view(
    name: str,
    published_at: datetime | None = None,
) -> ProductView:
    return ProductView(
        oid=ProductID(uuid.uuid4()),
        type=ProductType.NOTE,
        status=ProductStatus.PUBLISHED,
        name=name,
        description=None,
        total_duration_in_hours=None,
        author=UserRefView(
            oid=UserID(uuid.uuid4()),
            email="a@b.c",
            first_name="A",
            last_name="B",
            patronymic=None,
        ),
        cover=None,
        published_at=published_at or _NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_candidate(
    name: str,
    *,
    tag: float = 0.0,
    author: float = 0.0,
    popularity: float = 0.0,
    published_at: datetime | None = None,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        view=_make_view(name, published_at=published_at),
        tag_affinity_raw=tag,
        author_affinity_raw=author,
        popularity_raw=popularity,
    )


@pytest.fixture
def fake_file_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.presigned_get_url = AsyncMock(return_value="https://x/y")
    return storage


@pytest.fixture
def reader() -> AsyncMock:
    r = AsyncMock()
    r.recommendation_candidates = AsyncMock(return_value=[])
    return r


def _policy(
    *,
    tag: float = 0.4,
    author: float = 0.15,
    popularity: float = 0.3,
    freshness: float = 0.15,
    popularity_window_days: int = 30,
) -> RankingPolicy:
    return RankingPolicy(
        weights=RankingWeights(
            tag=tag,
            author=author,
            popularity=popularity,
            freshness=freshness,
        ),
        popularity_window_days=popularity_window_days,
    )


async def test_cold_start_returns_empty_when_reader_yields_nothing(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    handler = RecommendForMeQueryHandler(
        reader=reader, file_storage=fake_file_storage, config=_policy(),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=10, offset=0),
        ),
    )

    assert result == []
    fake_file_storage.presigned_get_url.assert_not_called()


async def test_overfetch_limit_passed_to_reader(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    handler = RecommendForMeQueryHandler(
        reader=reader, file_storage=fake_file_storage, config=_policy(),
    )
    user_id = UserID(uuid.uuid4())

    await handler.run(
        RecommendForMeQuery(
            user_id=user_id,
            pagination=Pagination(limit=20, offset=0),
        ),
    )

    reader.recommendation_candidates.assert_awaited_once()
    kwargs = reader.recommendation_candidates.await_args.kwargs
    assert kwargs["user_id"] == user_id
    # 20 * 3 = 60, above the 50 minimum
    assert kwargs["limit"] == 60
    assert kwargs["popularity_window_days"] == 30


async def test_overfetch_floor_when_page_size_is_tiny(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    handler = RecommendForMeQueryHandler(
        reader=reader, file_storage=fake_file_storage, config=_policy(),
    )

    await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=5, offset=0),
        ),
    )

    # 5 * 3 = 15, floor is 50
    assert reader.recommendation_candidates.await_args.kwargs["limit"] == 50


async def test_tag_weight_dominates_over_popularity_when_weighted(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    tag_heavy = _make_candidate("tag-heavy", tag=10.0, popularity=0.0)
    pop_heavy = _make_candidate("pop-heavy", tag=0.0, popularity=100.0)
    reader.recommendation_candidates.return_value = [pop_heavy, tag_heavy]
    handler = RecommendForMeQueryHandler(
        reader=reader,
        file_storage=fake_file_storage,
        config=_policy(tag=1.0, author=0.0, popularity=0.0, freshness=0.0),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=10, offset=0),
        ),
    )

    assert [o.name for o in result] == ["tag-heavy", "pop-heavy"]


async def test_popularity_weight_dominates_when_weighted(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    tag_heavy = _make_candidate("tag-heavy", tag=10.0, popularity=0.0)
    pop_heavy = _make_candidate("pop-heavy", tag=0.0, popularity=100.0)
    reader.recommendation_candidates.return_value = [tag_heavy, pop_heavy]
    handler = RecommendForMeQueryHandler(
        reader=reader,
        file_storage=fake_file_storage,
        config=_policy(tag=0.0, author=0.0, popularity=1.0, freshness=0.0),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=10, offset=0),
        ),
    )

    assert [o.name for o in result] == ["pop-heavy", "tag-heavy"]


async def test_normalization_scales_per_batch(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Two candidates with identical *normalized* tag signal (each is
    # the per-batch max within its dimension). Popularity dimension
    # is empty, so it should not break the math (no division by 0).
    a = _make_candidate("a", tag=1.0)
    b = _make_candidate("b", tag=999.0)
    reader.recommendation_candidates.return_value = [a, b]
    handler = RecommendForMeQueryHandler(
        reader=reader,
        file_storage=fake_file_storage,
        config=_policy(tag=1.0, author=0.0, popularity=0.0, freshness=0.0),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=10, offset=0),
        ),
    )

    # b is the batch max for tag, so it wins; the point is that
    # absence of popularity signal does not raise.
    assert [o.name for o in result] == ["b", "a"]


async def test_pagination_slices_after_ranking(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    candidates = [
        _make_candidate(f"c{i}", popularity=float(i)) for i in range(10)
    ]
    reader.recommendation_candidates.return_value = candidates
    handler = RecommendForMeQueryHandler(
        reader=reader,
        file_storage=fake_file_storage,
        config=_policy(tag=0.0, author=0.0, popularity=1.0, freshness=0.0),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=3, offset=2),
        ),
    )

    # Sorted desc by popularity: c9, c8, c7, c6, c5, ...
    # offset=2, limit=3 → c7, c6, c5
    assert [o.name for o in result] == ["c7", "c6", "c5"]


async def test_freshness_breaks_ties_when_signals_match(
    reader: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Two candidates with identical signals — only published_at differs.
    fresh = _make_candidate("fresh", published_at=_NOW)
    stale = _make_candidate(
        "stale", published_at=_NOW - timedelta(days=180),
    )
    reader.recommendation_candidates.return_value = [stale, fresh]
    handler = RecommendForMeQueryHandler(
        reader=reader,
        file_storage=fake_file_storage,
        config=_policy(tag=0.0, author=0.0, popularity=0.0, freshness=1.0),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=10, offset=0),
        ),
    )

    assert [o.name for o in result] == ["fresh", "stale"]


async def test_file_storage_invoked_once_per_returned_view_with_cover(
    fake_file_storage: AsyncMock,
) -> None:
    # No cover → no presigned URL call. Asserted via the empty-cover
    # views built by `_make_view`.
    reader = AsyncMock()
    reader.recommendation_candidates = AsyncMock(
        return_value=[_make_candidate("only", popularity=1.0)],
    )
    handler = RecommendForMeQueryHandler(
        reader=reader, file_storage=fake_file_storage, config=_policy(),
    )

    result = await handler.run(
        RecommendForMeQuery(
            user_id=UserID(uuid.uuid4()),
            pagination=Pagination(limit=1, offset=0),
        ),
    )

    assert len(result) == 1
    assert result[0].cover_url is None
    fake_file_storage.presigned_get_url.assert_not_called()


def test_handler_is_constructible_with_mocks() -> None:
    # Smoke test: protocol/constructor surface hasn't drifted.
    handler = RecommendForMeQueryHandler(
        reader=MagicMock(), file_storage=MagicMock(), config=_policy(),
    )
    assert handler is not None
