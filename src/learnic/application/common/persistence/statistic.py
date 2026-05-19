from typing import Protocol

from learnic.entities.statistic.models import Statistic


class StatisticGateway(Protocol):
    """Write-side persistence Protocol for :class:`Statistic`.

    Implementations persist the parent ``statistics`` row and the
    matching ``statistic_<type>`` subtype row inside the same
    caller transaction. Caller drives commit — the gateway never
    commits or flushes on its own.
    """

    async def add(self, statistic: Statistic) -> None: ...
