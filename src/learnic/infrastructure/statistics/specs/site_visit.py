"""Spec for ``site_visit`` — the activity signal behind DAU / MAU."""

from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.entities.statistic.details import SiteVisitDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistic_site_visit_table,
)
from learnic.infrastructure.statistics.specs._spec import StatisticTypeSpec

_ONE_DAY_SECONDS: int = 24 * 60 * 60


@final
class SiteVisitSpec(StatisticTypeSpec[SiteVisitDetails]):
    type: ClassVar[StatisticType] = StatisticType.SITE_VISIT
    details_cls: ClassVar[type] = SiteVisitDetails
    table: ClassVar[sa.Table] = statistic_site_visit_table
    # Collapse to at most one row per user per UTC day — the dedup
    # key is date-bucketed, so the window only needs to outlive a
    # single day for the Redis slot to survive it.
    dedupe_window_seconds: ClassVar[int] = _ONE_DAY_SECONDS

    @override
    def insert_values(
        self,
        statistic: Statistic,
        details: SiteVisitDetails,  # noqa: ARG002
    ) -> dict[str, Any]:
        return {
            "statistic_id": statistic.oid,
            "type": statistic.type.value,
        }

    @override
    def dedupe_key(
        self,
        statistic: Statistic,
        details: SiteVisitDetails,  # noqa: ARG002
    ) -> str | None:
        day = statistic.created_at.date().isoformat()
        return f"stat:{self.type.value}:{statistic.actor_id}:{day}"
