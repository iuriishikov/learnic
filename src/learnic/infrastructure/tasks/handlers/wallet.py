from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.wallet.release_ripe import (
    ReleaseRipeFreezesCommandHandler,
)
from learnic.infrastructure.tasks.broker import broker


@broker.task(schedule=[{"cron": "* * * * *"}])
@inject(patch_module=True)
async def release_ripe_freezes_task(
    handler: FromDishka[ReleaseRipeFreezesCommandHandler],
) -> None:
    """Periodic worker that turns ripe freezes into available balance.

    Triggered every minute by the ``taskiq scheduler`` process
    (``poetry run taskiq scheduler learnic.worker:broker``). The
    cron-label ``* * * * *`` is read by ``LabelScheduleSource`` and
    placed onto the broker queue; whichever worker picks it up
    delegates to :class:`ReleaseRipeFreezesCommandHandler`, which
    grabs a bounded batch with ``FOR UPDATE SKIP LOCKED`` so two
    overlapping ticks share the work instead of racing.

    The task is intentionally parameterless — the handler's batch
    limit is encoded in the handler itself; no scheduling cadence
    leaks into application code.
    """
    await handler.run()
