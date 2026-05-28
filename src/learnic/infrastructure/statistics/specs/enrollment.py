"""Spec for ``enrollment`` — a student joined a product."""

from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.entities.statistic.details import EnrollmentDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistic_enrollment_table,
)
from learnic.infrastructure.statistics.specs._spec import StatisticTypeSpec


@final
class EnrollmentSpec(StatisticTypeSpec[EnrollmentDetails]):
    type: ClassVar[StatisticType] = StatisticType.ENROLLMENT
    details_cls: ClassVar[type] = EnrollmentDetails
    table: ClassVar[sa.Table] = statistic_enrollment_table
    # Enrollment is a deliberate one-time action (the "already
    # enrolled?" gate lives in EnrollmentService); a fresh event
    # always represents a real new enrollment, so no dedup.
    dedupe_window_seconds: ClassVar[int] = 0

    @override
    def insert_values(
        self,
        statistic: Statistic,
        details: EnrollmentDetails,
    ) -> dict[str, Any]:
        return {
            "statistic_id": statistic.oid,
            "type": statistic.type.value,
            "product_id": details.product_id,
        }

    @override
    def dedupe_key(
        self,
        statistic: Statistic,  # noqa: ARG002
        details: EnrollmentDetails,  # noqa: ARG002
    ) -> str | None:
        return None
