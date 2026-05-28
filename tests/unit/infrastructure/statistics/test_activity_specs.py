import uuid
from datetime import datetime, timezone

from learnic.entities.product.ids import ProductID
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.entities.user.models import UserID
from learnic.infrastructure.statistics.specs import default_registry
from learnic.infrastructure.statistics.specs.enrollment import EnrollmentSpec
from learnic.infrastructure.statistics.specs.registration import (
    RegistrationSpec,
)
from learnic.infrastructure.statistics.specs.site_visit import SiteVisitSpec


def test_default_registry_covers_every_type() -> None:
    registry = default_registry()
    for stat_type in StatisticType:
        assert registry.by_type(stat_type) is not None


def test_registration_spec_never_dedups() -> None:
    spec = RegistrationSpec()
    actor = UserID(uuid.uuid4())
    stat = Statistic.for_registration(actor_id=actor)
    assert spec.dedupe_key(stat, stat.details) is None
    assert spec.insert_values(stat, stat.details) == {
        "statistic_id": stat.oid,
        "type": StatisticType.REGISTRATION.value,
    }


def test_enrollment_spec_carries_product_and_never_dedups() -> None:
    spec = EnrollmentSpec()
    actor = UserID(uuid.uuid4())
    product_id = ProductID(uuid.uuid4())
    stat = Statistic.for_enrollment(actor_id=actor, product_id=product_id)
    assert spec.dedupe_key(stat, stat.details) is None
    assert spec.insert_values(stat, stat.details) == {
        "statistic_id": stat.oid,
        "type": StatisticType.ENROLLMENT.value,
        "product_id": product_id,
    }


def test_site_visit_dedup_key_is_per_user_per_day() -> None:
    spec = SiteVisitSpec()
    actor = UserID(uuid.uuid4())
    other = UserID(uuid.uuid4())
    day_one_morning = datetime(2026, 5, 26, 8, 0, tzinfo=timezone.utc)
    day_one_evening = datetime(2026, 5, 26, 22, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)

    stat_morning = Statistic.for_site_visit(actor_id=actor, now=day_one_morning)
    stat_evening = Statistic.for_site_visit(actor_id=actor, now=day_one_evening)
    stat_next_day = Statistic.for_site_visit(actor_id=actor, now=day_two)
    stat_other = Statistic.for_site_visit(actor_id=other, now=day_one_morning)

    key_morning = spec.dedupe_key(stat_morning, stat_morning.details)
    key_evening = spec.dedupe_key(stat_evening, stat_evening.details)
    key_next_day = spec.dedupe_key(stat_next_day, stat_next_day.details)
    key_other = spec.dedupe_key(stat_other, stat_other.details)

    # same user, same UTC day -> collapsed
    assert key_morning == key_evening
    # same user, different day -> distinct
    assert key_morning != key_next_day
    # different user, same day -> distinct
    assert key_morning != key_other
    assert key_morning == f"stat:site_visit:{actor}:2026-05-26"
