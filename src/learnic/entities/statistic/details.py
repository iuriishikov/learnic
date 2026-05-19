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
