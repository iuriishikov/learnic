"""Per-type statistic specs and the registry that bundles them.

Adding a new statistic type:

1. Append a value to :class:`StatisticType`.
2. Add a ``<Type>Details`` subclass in
   ``entities/statistic/details.py``.
3. Add a ``Statistic.for_<type>(...)`` class method in
   ``entities/statistic/models.py``.
4. Add a ``statistic_<type>_table`` in
   ``infrastructure/persistence/models/statistic.py`` (composite
   FK + CHECK by the established pattern).
5. Add a ``<Type>Spec`` here implementing
   :class:`StatisticTypeSpec`, then append it to
   :func:`default_registry`. The registry's exhaustiveness check
   fails the app boot if step 5 is forgotten.
6. Ship an Alembic migration adding the enum value (sole-transaction
   ALTER TYPE … ADD VALUE) plus the new subtype table.
"""

from typing import Any

from learnic.infrastructure.statistics.specs._spec import (
    StatisticTypeRegistry,
    StatisticTypeSpec,
)
from learnic.infrastructure.statistics.specs.enrollment import (
    EnrollmentSpec,
)
from learnic.infrastructure.statistics.specs.product_view import (
    ProductViewSpec,
)
from learnic.infrastructure.statistics.specs.profile_view import (
    ProfileViewSpec,
)
from learnic.infrastructure.statistics.specs.registration import (
    RegistrationSpec,
)
from learnic.infrastructure.statistics.specs.site_visit import (
    SiteVisitSpec,
)


def default_registry() -> StatisticTypeRegistry:
    """Build the registry containing every statistic type shipped today."""
    specs: list[StatisticTypeSpec[Any]] = [
        ProfileViewSpec(),
        ProductViewSpec(),
        RegistrationSpec(),
        EnrollmentSpec(),
        SiteVisitSpec(),
    ]
    return StatisticTypeRegistry(specs)


__all__ = [
    "EnrollmentSpec",
    "ProductViewSpec",
    "ProfileViewSpec",
    "RegistrationSpec",
    "SiteVisitSpec",
    "default_registry",
]
