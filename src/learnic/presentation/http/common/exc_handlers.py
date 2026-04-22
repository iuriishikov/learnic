from http import HTTPStatus
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from learnic.application.common.errors import (
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    EntityNotFoundError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from learnic.entities.common.errors import FieldError


async def _field_error_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    # Registered for FieldError, so the runtime type is guaranteed.
    fields = {k: v for k, v in exc.__dict__.items() if not k.startswith("_")}
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"error": type(exc).__name__, **fields},
    )


async def _entity_not_found_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, EntityNotFoundError)
    return JSONResponse(
        status_code=HTTPStatus.NOT_FOUND,
        content={
            "error": "EntityNotFound",
            "entity_id": str(exc.entity_id),
        },
    )


def _status_handler(
    status: HTTPStatus, error: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": error})

    return handler


def map_exc_handlers(app: FastAPI) -> None:
    """Translate domain/application errors into HTTP responses.

    Keep this centralized — routes must NOT raise ``HTTPException``;
    they let domain/application errors bubble up and this mapper turns
    them into proper status codes.
    """
    app.add_exception_handler(FieldError, _field_error_handler)
    app.add_exception_handler(EntityNotFoundError, _entity_not_found_handler)
    app.add_exception_handler(
        InvalidCredentialsError,
        _status_handler(HTTPStatus.UNAUTHORIZED, "InvalidCredentials"),
    )
    app.add_exception_handler(
        InvalidTokenError,
        _status_handler(HTTPStatus.UNAUTHORIZED, "InvalidToken"),
    )
    app.add_exception_handler(
        EmailAlreadyRegisteredError,
        _status_handler(HTTPStatus.CONFLICT, "EmailAlreadyRegistered"),
    )
    app.add_exception_handler(
        EmailNotVerifiedError,
        _status_handler(HTTPStatus.FORBIDDEN, "EmailNotVerified"),
    )
