"""Spec for ``registration`` — a new account was created."""

from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.entities.statistic.details import RegistrationDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistic_registration_table,
)
from learnic.infrastructure.statistics.specs._spec import StatisticTypeSpec


@final
class RegistrationSpec(StatisticTypeSpec[RegistrationDetails]):
    type: ClassVar[StatisticType] = StatisticType.REGISTRATION
    details_cls: ClassVar[type] = RegistrationDetails
    table: ClassVar[sa.Table] = statistic_registration_table
    # Every registration is a distinct, one-off event — no dedup.
    dedupe_window_seconds: ClassVar[int] = 0

    @override
    def insert_values(
        self,
        statistic: Statistic,
        details: RegistrationDetails,  # noqa: ARG002
    ) -> dict[str, Any]:
        return {
            "statistic_id": statistic.oid,
            "type": statistic.type.value,
        }

    @override
    def dedupe_key(
        self,
        statistic: Statistic,  # noqa: ARG002
        details: RegistrationDetails,  # noqa: ARG002
    ) -> str | None:
        return None
