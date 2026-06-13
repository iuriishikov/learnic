import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import (
    ProductReader,
    RecommendationCandidate,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    ProductOutput,
    resolve_product_output,
)
from learnic.entities.user.models import UserID

_OVERFETCH_MULTIPLIER: Final = 3
_MIN_OVERFETCH_LIMIT: Final = 50
_FRESHNESS_HALF_LIFE_DAYS: Final = 30


@dataclass(slots=True, frozen=True)
class RankingWeights:
    """Linear blend weights for the four ranking signals.

    Weights are not constrained to sum to ``1`` — only their ratios
    matter once each signal has been max-scaled to ``[0, 1]`` inside
    the handler. Tuned via ``RECOMMENDATIONS_WEIGHT_*`` env vars
    (see ``RecommendationsConfig`` in ``infrastructure/configs.py``)
    without code changes so A/B experiments are a redeploy, not a
    release.
    """

    tag: float
    author: float
    popularity: float
    freshness: float


@dataclass(slots=True, frozen=True)
class RecommendForMeQuery:
    user_id: UserID
    pagination: Pagination


@dataclass(slots=True, frozen=True)
class RankingPolicy:
    """Application-layer DTO for tuning the recommender at runtime.

    Mirrors the env-fed ``RecommendationsConfig`` BaseSettings in
    ``infrastructure/configs.py`` but exposed as a plain frozen
    dataclass so the application layer never imports
    ``BaseSettings`` (rule 1: no infrastructure leakage). Built
    by ``ConfigsProvider.ranking_policy`` from the env block.
    """

    weights: RankingWeights
    popularity_window_days: int


@final
class RecommendForMeQueryHandler:
    """Rank published products for the current user.

    The Reader returns raw signal counts; this handler:

    1. **max-scales** every signal to ``[0, 1]`` inside the current
       batch so a high-popularity outlier cannot drown out a strong
       tag-affinity match,
    2. mixes them with :class:`RankingWeights`,
    3. adds an exponential-decay freshness bias keyed on
       ``published_at`` so newly-published products surface even
       before they have signal,
    4. slices the result for the requested pagination page.

    Cold start is handled implicitly: a user with no enrollments
    yields a profile with zero tag/author signal, so ranking
    collapses to ``popularity + freshness`` — i.e. "top of the
    platform right now," which is the right default for a
    first-time visitor.
    """

    def __init__(
        self,
        reader: ProductReader,
        file_storage: FileStorage,
        config: RankingPolicy,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage
        self._config: Final = config

    async def run(
        self,
        data: RecommendForMeQuery,
    ) -> list[ProductOutput]:
        # Overfetch must cover the requested page's offset, not just its
        # limit — otherwise a deep page (offset + limit beyond the window)
        # slices off the tail or comes back empty even though more ranked
        # candidates exist.
        overfetch = max(
            _MIN_OVERFETCH_LIMIT,
            data.pagination.offset
            + data.pagination.limit * _OVERFETCH_MULTIPLIER,
        )
        candidates = await self._reader.recommendation_candidates(
            user_id=data.user_id,
            limit=overfetch,
            popularity_window_days=self._config.popularity_window_days,
        )
        if not candidates:
            return []

        scaled = _max_scale(candidates)
        now = datetime.now(timezone.utc)
        ranked = sorted(
            candidates,
            key=lambda c: self._score(c, scaled, now),
            reverse=True,
        )
        page = ranked[
            data.pagination.offset
            : data.pagination.offset + data.pagination.limit
        ]
        return [
            await resolve_product_output(c.view, self._file_storage)
            for c in page
        ]

    def _score(
        self,
        c: RecommendationCandidate,
        scaled: "_MaxScale",
        now: datetime,
    ) -> float:
        w = self._config.weights
        return (
            w.tag * scaled.tag(c.tag_affinity_raw)
            + w.author * scaled.author(c.author_affinity_raw)
            + w.popularity * scaled.popularity(c.popularity_raw)
            + w.freshness * _freshness_boost(c.view.published_at, now)
        )


@dataclass(slots=True, frozen=True)
class _MaxScale:
    """Per-batch max-scaler. Returns 0 when the batch max is 0."""

    tag_max: float
    author_max: float
    popularity_max: float

    def tag(self, raw: float) -> float:
        return raw / self.tag_max if self.tag_max > 0 else 0.0

    def author(self, raw: float) -> float:
        return raw / self.author_max if self.author_max > 0 else 0.0

    def popularity(self, raw: float) -> float:
        return raw / self.popularity_max if self.popularity_max > 0 else 0.0


def _max_scale(candidates: list[RecommendationCandidate]) -> _MaxScale:
    return _MaxScale(
        tag_max=max((c.tag_affinity_raw for c in candidates), default=0.0),
        author_max=max(
            (c.author_affinity_raw for c in candidates), default=0.0,
        ),
        popularity_max=max(
            (c.popularity_raw for c in candidates), default=0.0,
        ),
    )


def _freshness_boost(
    published_at: datetime | None,
    now: datetime,
) -> float:
    """Exponential decay on days-since-publish.

    Half-life is ``_FRESHNESS_HALF_LIFE_DAYS``: a 30-day-old product
    contributes ~37% of a same-day publish under the freshness
    weight. Returns 0 for products with no ``published_at`` (they
    should not appear in the candidate pool, but defensive).
    """
    if published_at is None:
        return 0.0
    delta = now - published_at
    days = max(0.0, delta.total_seconds() / 86400.0)
    return math.exp(-days / _FRESHNESS_HALF_LIFE_DAYS)
