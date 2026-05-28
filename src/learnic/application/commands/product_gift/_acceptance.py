"""Shared post-transition logic for the two gift-accept handlers.

Both the email-token accept and the in-app accept converge here
once the :class:`ProductGift` has been transitioned to ``ACCEPTED``
in memory: validate the product is still enrollable, create the
enrollment via :class:`EnrollmentService`, notify the gifter, and
republish the recipient's own card so it flips to resolved in real
time.
"""

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    CourseEnrollmentTarget,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInUnpublishedProductError,
    EntityNotFoundError,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    GiftAcceptedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import UserID


async def check_product_enrollable(
    gift: ProductGift,
    product_gateway: ProductGateway,
) -> None:
    """Reject acceptance when the gifted product is no longer enrollable.

    Raised before the in-memory accept transition is committed, so a
    failed check leaves the gift pending.
    """
    product = await product_gateway.with_id(gift.product_id)
    if product is None:
        raise EntityNotFoundError(gift.product_id)
    if product.status is not ProductStatus.PUBLISHED:
        raise CannotEnrollInUnpublishedProductError(
            product_id=product.oid,
            status=product.status.value,
        )


async def finalize_acceptance(
    *,
    gift: ProductGift,
    actor_id: UserID,
    enrollment_service: EnrollmentService,
    transaction: Transaction,
    notifications: NotificationPublisher,
    event_bus: ProductEventBus,
) -> None:
    """Create the enrollment and fan out the acceptance notifications.

    Call after ``gift.accept(...)`` / ``gift.accept_in_app(...)`` has
    transitioned the entity. :meth:`EnrollmentService.enroll` commits
    the unit of work (persisting the accept alongside the new
    enrollment); if the recipient is already enrolled the gift is
    still committed as accepted — the gift goal (access) is already
    met. After the commit a ``gift_accepted`` product event lets
    collaborators watching the editor see the gift flip to resolved.
    """
    try:
        await enrollment_service.enroll(
            student_id=actor_id,
            target=CourseEnrollmentTarget(product_id=gift.product_id),
        )
    except AlreadyEnrolledError:
        await transaction.commit()
    await publish_product_event(
        event_bus,
        payload=GiftAcceptedPayload.of(gift.oid),
        product_id=gift.product_id,
        actor_id=actor_id,
    )
    await notifications.publish(
        Notification.for_gift_accepted(
            recipient_id=gift.invited_by,
            actor_id=actor_id,
            gift_id=gift.oid,
            product_id=gift.product_id,
            gift_recipient_id=actor_id,
        ),
    )
    await notifications.republish_for_gift(
        recipient_id=actor_id,
        gift_id=gift.oid,
    )
