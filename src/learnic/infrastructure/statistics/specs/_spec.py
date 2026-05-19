"""Per-type specification — single source of truth for a statistic type.

A spec bundles everything that varies between :class:`StatisticType`
values: the matching ``StatisticDetails`` subclass, the
``statistic_<type>`` SA table, and the SA Core ``INSERT`` payload
builder. The gateway dispatches through the registry so adding a
new type means writing one spec file (and one table + Alembic
migration) — gateway, collector, and DI wiring are unchanged.

Lives entirely in infrastructure because statistics are write-only
at the moment: the application layer has no need to dispatch on
type. If reads ever require type-specific projection, the
application-side half can be lifted into
``application/common/statistics/type_spec.py`` the same way
``NotificationKindSpec`` is split today.
"""

from typing import Any, ClassVar, Final, Protocol, TypeVar

import sqlalchemy as sa

from learnic.entities.statistic.details import StatisticDetails
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic

D = TypeVar("D", bound=StatisticDetails)


class StatisticTypeSpec(Protocol[D]):
    """Contract every concrete ``<type>Spec`` class implements.

    Each spec lives in its own ``specs/<type>.py`` module and is
    listed once in :func:`default_registry`. The gateway resolves
    a spec by ``details_cls`` on writes (driven by the entity
    factory the caller invoked) and by ``type`` on reads (driven
    by the parent row's discriminator).

    Two responsibilities:

    - **Persistence** — ``table`` + :meth:`insert_values` describe
      how the subtype row is written.
    - **Dedup** — :attr:`dedupe_window_seconds` and
      :meth:`dedupe_key` decide whether a fresh event is collapsed
      into a recent one from the same actor. Each concrete spec
      MUST declare its own window — there is no shared default,
      because the right "what counts as a duplicate?" interval
      depends entirely on the event type (page open vs. webinar
      join vs. lesson complete). Setting the window to ``0`` opts
      the type out of dedup entirely.
    """

    type: ClassVar[StatisticType]
    details_cls: ClassVar[type]
    table: ClassVar[sa.Table]
    dedupe_window_seconds: ClassVar[int]

    def insert_values(
        self,
        statistic: Statistic,
        details: D,
    ) -> dict[str, Any]:
        """Build the ``INSERT`` payload for the subtype row.

        Includes ``statistic_id`` and ``type`` (the composite FK
        target) plus every type-specific column.
        """
        ...

    def dedupe_key(
        self,
        statistic: Statistic,
        details: D,
    ) -> str | None:
        """Return the dedup key for this event, or ``None`` to skip dedup.

        Two events with the same key within
        :attr:`dedupe_window_seconds` are collapsed — the first
        wins, subsequent ones are dropped. Keys live in a shared
        keyspace across types, so concrete specs MUST namespace
        their keys with the type value (e.g.
        ``f"stat:{self.type.value}:{actor_id}:{target_id}"``).

        Returning ``None`` short-circuits dedup for this specific
        event even if the window is non-zero — useful when the
        details do not identify a "same page" the way duplicate
        suppression normally implies.
        """
        ...


class StatisticTypeRegistry:
    """Lookup table: type ↔ details class ↔ spec.

    Construction validates two invariants and fails fast:

    - **No duplicates** — each :class:`StatisticType` and each
      details class is registered exactly once. A duplicate
      registration is a programming error.
    - **Exhaustiveness** — every :class:`StatisticType` value has
      a registered spec. A missing spec is a deployment bug we
      want surfaced at app boot, not on the first event of the
      forgotten type.
    """

    def __init__(self, specs: list[StatisticTypeSpec[Any]]) -> None:
        by_type: dict[StatisticType, StatisticTypeSpec[Any]] = {}
        by_details: dict[type, StatisticTypeSpec[Any]] = {}
        for spec in specs:
            if spec.type in by_type:
                raise ValueError(
                    f"Duplicate statistic type in registry: {spec.type!r}",
                )
            if spec.details_cls in by_details:
                raise ValueError(
                    "Duplicate statistic details class in registry: "
                    f"{spec.details_cls.__name__}",
                )
            by_type[spec.type] = spec
            by_details[spec.details_cls] = spec
        missing = set(StatisticType) - by_type.keys()
        if missing:
            raise RuntimeError(
                "Statistic type registry incomplete; missing specs for: "
                f"{sorted(t.value for t in missing)}",
            )
        self._by_type: Final = by_type
        self._by_details: Final = by_details

    def by_type(
        self,
        statistic_type: StatisticType,
    ) -> StatisticTypeSpec[Any]:
        try:
            return self._by_type[statistic_type]
        except KeyError as exc:
            raise LookupError(
                f"No spec registered for statistic type: {statistic_type!r}",
            ) from exc

    def by_details_type(
        self,
        details_cls: type,
    ) -> StatisticTypeSpec[Any]:
        try:
            return self._by_details[details_cls]
        except KeyError as exc:
            raise LookupError(
                "No spec registered for statistic details type: "
                f"{details_cls.__name__}",
            ) from exc
