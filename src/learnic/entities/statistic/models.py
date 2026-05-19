import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.statistic.details import (
    ProductViewDetails,
    ProfileViewDetails,
    StatisticDetails,
)
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.ids import StatisticID
from learnic.entities.user.models import UserID


@dataclass
class Statistic(BaseEntity[StatisticID]):
    """A single recorded statistic event.

    The base row carries the fields every event needs — actor
    (the authenticated user who triggered the event), discriminator
    (``type``), creation timestamp. The polymorphic body lives in
    :attr:`details`, mapped to a subtype table picked by ``type``.

    Construction is always through the typed ``for_<type>`` class
    methods — callers never instantiate ``Statistic`` directly,
    which makes "type does not match details shape" impossible at
    compile time. Adding a new type means adding a new class method
    here next to the new ``StatisticDetails`` subclass.
    """

    type: StatisticType
    actor_id: UserID
    created_at: datetime
    details: StatisticDetails = field(default_factory=StatisticDetails)

    @classmethod
    def for_profile_view(
        cls,
        *,
        actor_id: UserID,
        target_user_id: UserID,
        referrer: str | None = None,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=StatisticID(uuid.uuid4()),
            type=StatisticType.PROFILE_VIEW,
            actor_id=actor_id,
            created_at=moment,
            details=ProfileViewDetails(
                target_user_id=target_user_id,
                referrer=referrer,
            ),
        )

    @classmethod
    def for_product_view(
        cls,
        *,
        actor_id: UserID,
        product_id: ProductID,
        referrer: str | None = None,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=StatisticID(uuid.uuid4()),
            type=StatisticType.PRODUCT_VIEW,
            actor_id=actor_id,
            created_at=moment,
            details=ProductViewDetails(
                product_id=product_id,
                referrer=referrer,
            ),
        )
