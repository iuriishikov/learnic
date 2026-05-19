"""Spec for ``product_view`` — recipient opened a product page."""

from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.entities.statistic.details import ProductViewDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistic_product_view_table,
)
from learnic.infrastructure.statistics.specs._spec import StatisticTypeSpec


@final
class ProductViewSpec(StatisticTypeSpec[ProductViewDetails]):
    type: ClassVar[StatisticType] = StatisticType.PRODUCT_VIEW
    details_cls: ClassVar[type] = ProductViewDetails
    table: ClassVar[sa.Table] = statistic_product_view_table
    dedupe_window_seconds: ClassVar[int] = 60

    @override
    def insert_values(
        self,
        statistic: Statistic,
        details: ProductViewDetails,
    ) -> dict[str, Any]:
        return {
            "statistic_id": statistic.oid,
            "type": statistic.type.value,
            "product_id": details.product_id,
            "referrer": details.referrer,
        }

    @override
    def dedupe_key(
        self,
        statistic: Statistic,
        details: ProductViewDetails,
    ) -> str | None:
        return (
            f"stat:{self.type.value}:"
            f"{statistic.actor_id}:{details.product_id}"
        )
