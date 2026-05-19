from enum import StrEnum


class StatisticType(StrEnum):
    """Discriminator for the polymorphic statistic body.

    Each type maps to exactly one subtype table in
    :mod:`learnic.infrastructure.persistence.models.statistic`
    and to one :class:`StatisticDetails` subclass. Adding a new
    type means: append a value here, add a ``StatisticDetails``
    subclass, add a ``statistic_<type>`` subtype table, register a
    spec in
    :func:`learnic.infrastructure.statistics.specs.default_registry`.
    The registry's exhaustiveness check fails fast at app boot if
    any of those steps is missed.
    """

    PROFILE_VIEW = "profile_view"
    PRODUCT_VIEW = "product_view"
