from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    NotAWebinarError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import (
    AccessWindow,
    ParticipantsLimit,
    StreamUrl,
    WebinarLessonsCount,
    WebinarSessionDuration,
)
from learnic.entities.product.webinar_details import WebinarDetails
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateWebinarDefaultsCommand:
    actor_id: UserID
    product_id: ProductID
    total_lessons: int
    default_duration_minutes: int
    allow_recording: bool
    default_max_participants: int | None
    default_stream_url: str | None
    access_window_minutes: int | None


@final
class UpdateWebinarDefaultsCommandHandler:
    """PUT-style replace of all webinar defaults on a product.

    Loads the product (which transparently hydrates
    ``webinar_details`` for webinar products) and rewrites every
    field on the sub-entity in one transaction. If the webinar was
    created without defaults, this handler creates the
    ``WebinarDetails`` row on first call. Refuses on course
    products with :class:`NotAWebinarError`.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway

    async def run(self, data: UpdateWebinarDefaultsCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_DESCRIPTION,
        )
        if product.type is not ProductType.WEBINAR:
            raise NotAWebinarError(data.product_id)

        total_lessons = WebinarLessonsCount(data.total_lessons)
        default_duration = WebinarSessionDuration(data.default_duration_minutes)
        max_participants = (
            ParticipantsLimit(data.default_max_participants)
            if data.default_max_participants is not None
            else None
        )
        stream_url = (
            StreamUrl(data.default_stream_url)
            if data.default_stream_url is not None
            else None
        )
        access_window = (
            AccessWindow(data.access_window_minutes)
            if data.access_window_minutes is not None
            else None
        )

        if product.webinar_details is None:
            details = WebinarDetails.create(
                product_id=product.oid,
                total_lessons=total_lessons,
                default_duration_minutes=default_duration,
                allow_recording=data.allow_recording,
                default_max_participants=max_participants,
                default_stream_url=stream_url,
                access_window_minutes=access_window,
            )
            product.attach_webinar_details(details)
            self._entity_saver.add_one(details)
        else:
            details = product.webinar_details
            details.change_lessons_count(total_lessons)
            details.change_default_duration(default_duration)
            details.set_recording(data.allow_recording)
            details.change_default_max_participants(max_participants)
            details.change_default_stream_url(stream_url)
            details.change_access_window(access_window)

        await self._transaction.commit()
