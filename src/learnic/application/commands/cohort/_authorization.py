from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


async def assert_cohort_authorized(
    cohort: Cohort,
    actor_id: UserID,
    authorizer: Authorizer,
) -> None:
    """Raise if ``actor`` may not edit ``cohort``.

    A cohort is editable by either:

    * its ``host_id`` — the user running the sessions;
    * any caller with ``MANAGE_RELEASES`` on the parent webinar
      product (owner short-circuits inside the authorizer).

    The host check is cheap (single attribute compare) and runs
    first; the authorizer is consulted only when needed.

    Raises:
        InsufficientPermissionsError: Actor is neither the host nor
            holds ``MANAGE_RELEASES`` on the parent product.
    """
    if cohort.host_id == actor_id:
        return
    await authorizer.require(
        actor_id,
        AuthzTarget.for_product(cohort.webinar_id),
        Permission.MANAGE_RELEASES,
    )


async def assert_schedule_authorized(
    schedule: WebinarSchedule,
    actor_id: UserID,
    cohort_gateway: CohortGateway,
    authorizer: Authorizer,
) -> None:
    """Authorize a schedule mutation by delegating to the parent cohort.

    Loads the cohort the schedule belongs to and runs
    :func:`assert_cohort_authorized`.

    Raises:
        EntityNotFoundError: Parent cohort missing (FK violation).
        InsufficientPermissionsError: Actor is neither host nor
            holds ``MANAGE_RELEASES`` on the parent product.
    """
    cohort = await cohort_gateway.with_id(schedule.cohort_id)
    if cohort is None:
        raise EntityNotFoundError(schedule.cohort_id)
    await assert_cohort_authorized(cohort, actor_id, authorizer)


async def assert_session_authorized(
    session: WebinarSession,
    actor_id: UserID,
    cohort_gateway: CohortGateway,
    authorizer: Authorizer,
) -> None:
    """Authorize a session mutation by delegating to the parent cohort."""
    cohort = await cohort_gateway.with_id(session.cohort_id)
    if cohort is None:
        raise EntityNotFoundError(session.cohort_id)
    await assert_cohort_authorized(cohort, actor_id, authorizer)
