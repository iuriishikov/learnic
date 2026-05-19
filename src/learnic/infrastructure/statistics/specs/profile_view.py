"""Spec for ``profile_view`` — recipient opened a user's profile."""

from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.entities.statistic.details import ProfileViewDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistic_profile_view_table,
)
from learnic.infrastructure.statistics.specs._spec import StatisticTypeSpec


@final
class ProfileViewSpec(StatisticTypeSpec[ProfileViewDetails]):
    type: ClassVar[StatisticType] = StatisticType.PROFILE_VIEW
    details_cls: ClassVar[type] = ProfileViewDetails
    table: ClassVar[sa.Table] = statistic_profile_view_table
    dedupe_window_seconds: ClassVar[int] = 60

    @override
    def insert_values(
        self,
        statistic: Statistic,
        details: ProfileViewDetails,
    ) -> dict[str, Any]:
        return {
            "statistic_id": statistic.oid,
            "type": statistic.type.value,
            "target_user_id": details.target_user_id,
            "referrer": details.referrer,
        }

    @override
    def dedupe_key(
        self,
        statistic: Statistic,
        details: ProfileViewDetails,
    ) -> str | None:
        return (
            f"stat:{self.type.value}:"
            f"{statistic.actor_id}:{details.target_user_id}"
        )
