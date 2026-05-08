from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.user.models import UserID


async def assert_cohort_authorized(
    cohort: Cohort,
    actor_id: UserID,
    product_gateway: ProductGateway,
) -> None:
    """Raise :class:`NotResourceOwnerError` if ``actor`` may not edit ``cohort``.

    A cohort is editable by either:

    * its ``host_id`` — the user running the sessions;
    * the parent webinar product's ``author_id``.

    The host check is cheap (single attribute compare) and runs
    first; the product is loaded only when needed.

    Raises:
        NotResourceOwnerError: ``actor_id`` is neither the host nor
            the product's author.
    """
    if cohort.host_id == actor_id:
        return
    product = await product_gateway.with_id(cohort.webinar_id)
    if product is None or product.author_id != actor_id:
        raise NotResourceOwnerError(cohort.oid, actor_id)


async def assert_schedule_authorized(
    schedule: WebinarSchedule,
    actor_id: UserID,
    cohort_gateway: CohortGateway,
    product_gateway: ProductGateway,
) -> None:
    """Authorize a schedule mutation by delegating to the parent cohort.

    Loads the cohort the schedule belongs to and runs
    :func:`assert_cohort_authorized`.

    Raises:
        EntityNotFoundError: Parent cohort missing (FK violation).
        NotResourceOwnerError: Actor is neither host nor product
            author.
    """
    cohort = await cohort_gateway.with_id(schedule.cohort_id)
    if cohort is None:
        raise EntityNotFoundError(schedule.cohort_id)
    await assert_cohort_authorized(cohort, actor_id, product_gateway)


async def assert_session_authorized(
    session: WebinarSession,
    actor_id: UserID,
    cohort_gateway: CohortGateway,
    product_gateway: ProductGateway,
) -> None:
    """Authorize a session mutation by delegating to the parent cohort."""
    cohort = await cohort_gateway.with_id(session.cohort_id)
    if cohort is None:
        raise EntityNotFoundError(session.cohort_id)
    await assert_cohort_authorized(cohort, actor_id, product_gateway)
