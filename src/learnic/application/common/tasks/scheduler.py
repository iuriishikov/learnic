from typing import Protocol


class TaskScheduler(Protocol):
    """Enqueues background tasks from command handlers.

    Application handlers depend on this protocol to schedule work
    for later execution without knowing about the broker.
    Add one method per domain operation you need to enqueue.
    """

    async def schedule_example(self, payload: str) -> None: ...
