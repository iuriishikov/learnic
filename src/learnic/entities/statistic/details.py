from dataclasses import dataclass

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True)
class StatisticDetails:
    """Polymorphic body of a statistic event.

    Each concrete subclass corresponds to a row in a dedicated
    ``statistic_<type>`` subtype table. Subtype tables share the
    statistic id with the parent ``statistics`` row through a
    composite ``(statistic_id, type)`` foreign key — that enforces
    "profile-view-shaped subtype attaches only to a profile-view-
    type statistic" at the database level.
    """


@dataclass(slots=True)
class ProfileViewDetails(StatisticDetails):
    """Body for the ``profile_view`` statistic.

    Recorded when an authenticated user opens another user's public
    profile page. ``target_user_id`` is the profile owner; the
    viewer (actor) lives on the parent row. ``referrer`` is the
    optional HTTP ``Referer`` header truncated to
    :data:`REFERRER_MAX_LEN` so we can later distinguish in-app
    navigation from external traffic — ``None`` when the client
    did not send one (direct hit, cross-origin policy strip).
    """

    target_user_id: UserID
    referrer: str | None


@dataclass(slots=True)
class ProductViewDetails(StatisticDetails):
    """Body for the ``product_view`` statistic.

    Recorded when an authenticated user opens a product card /
    landing page. ``referrer`` follows the same semantics as in
    :class:`ProfileViewDetails`.
    """

    product_id: ProductID
    referrer: str | None


@dataclass(slots=True)
class RegistrationDetails(StatisticDetails):
    """Body for the ``registration`` statistic.

    Recorded once when a user account is created. The new user is
    the actor on the parent row, so there is no type-specific
    column to carry — the event's value is the actor + timestamp,
    which together drive the registrations-over-time series.
    """


@dataclass(slots=True)
class EnrollmentDetails(StatisticDetails):
    """Body for the ``enrollment`` statistic.

    Recorded when a student is enrolled into a product through any
    path (self-enroll, accepted gift, admin grant). The enrolling
    student is the actor on the parent row; ``product_id`` is the
    course they joined, so enrollments can be broken down per
    product.
    """

    product_id: ProductID


@dataclass(slots=True)
class SiteVisitDetails(StatisticDetails):
    """Body for the ``site_visit`` statistic.

    Recorded when an authenticated user loads the app (one row per
    user per UTC day, enforced by the spec's dedup key). Carries no
    type-specific column — the actor + day are the whole signal,
    and DAU / MAU are ``COUNT(DISTINCT actor_id)`` over the parent
    rows for the relevant window.
    """
