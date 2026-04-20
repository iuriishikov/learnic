from learnic.infrastructure.tasks.broker import broker


@broker.task
async def example_task(payload: str) -> None:
    """Run an example background job.

    Copy this pattern for new tasks. To inject an application
    handler, add ``@inject`` below ``@broker.task`` and declare
    ``handler: FromDishka[<HandlerType>]`` in the signature,
    then delegate via ``await handler.run(...)``.

    Args:
        payload: Arbitrary data the producer passed to ``.kiq(...)``.
    """
    _ = payload
