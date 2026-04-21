from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status
from pydantic import BaseModel

from learnic.application.commands.user.create import (
    CreateUserCommand,
    CreateUserCommandHandler,
)
from learnic.application.queries.user.get import (
    GetUserQuery,
    GetUserQueryHandler,
)
from learnic.entities.user.models import UserID

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=DishkaRoute,
)


class CreateUserSchema(BaseModel):
    email: str
    first_name: str
    last_name: str
    patronymic: str | None = None


class UserSchema(BaseModel):
    oid: UUID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    payload: CreateUserSchema,
    interactor: FromDishka[CreateUserCommandHandler],
) -> UUID:
    """Create a new user.

    Args:
        payload: Email and name fields validated by Pydantic at the
            HTTP boundary.

    Returns:
        The created user's identifier (UUID).

    Raises:
        FieldError: One of the name value-object invariants was
            violated (empty or too long); mapped to HTTP 422.
    """
    return await interactor.run(
        CreateUserCommand(
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            patronymic=payload.patronymic,
        ),
    )


@router.get("/{user_id}")
async def get(
    user_id: UUID,
    interactor: FromDishka[GetUserQueryHandler],
) -> UserSchema:
    """Return a user by id.

    Args:
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        A read-side projection of the user.

    Raises:
        EntityNotFoundError: No user with the given id; mapped to
            HTTP 404.
    """
    view = await interactor.run(GetUserQuery(oid=UserID(user_id)))
    return UserSchema(
        oid=view.oid,
        email=view.email,
        first_name=view.first_name,
        last_name=view.last_name,
        patronymic=view.patronymic,
    )
