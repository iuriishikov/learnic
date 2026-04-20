from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status

from learnic.application.queries.ping.ping import (
    PingOutput,
    PingQuery,
    PingQueryHandler,
)

router = APIRouter(
    prefix="/ping",
    tags=["Ping"],
    route_class=DishkaRoute,
)


@router.get("", status_code=status.HTTP_200_OK)
async def ping(
    interactor: FromDishka[PingQueryHandler],
) -> PingOutput:
    return await interactor.run(PingQuery())
