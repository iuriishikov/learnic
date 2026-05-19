from typing import Protocol

from learnic.entities.statistic.models import Statistic


class StatisticsCollector(Protocol):
    """Application-layer facade for recording statistic events.

    Routes, query handlers, and middleware depend on this Protocol
    and pass a fully-built :class:`Statistic` (constructed via one
    of the typed ``Statistic.for_<type>(...)`` factories). The
    implementation owns the persistence transaction so callers
    that have no transaction of their own (read-side query
    handlers, middleware) can record events without leaking
    transactional concerns out of the abstraction.

    Whether the implementation writes inline, batches, or
    enqueues onto a task queue is an infrastructure choice — the
    Protocol is identical either way, and switching is a single
    DI binding change.
    """

    async def record(self, statistic: Statistic) -> None: ...
