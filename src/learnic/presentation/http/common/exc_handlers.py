from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.common.errors import FieldError


async def _field_error_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    # Registered for FieldError, so the runtime type is guaranteed.
    fields = {
        k: v for k, v in exc.__dict__.items() if not k.startswith("_")
    }
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


def map_exc_handlers(app: FastAPI) -> None:
    """Translate domain/application errors into HTTP responses.

    Keep this centralized — routes must NOT raise ``HTTPException``;
    they let domain/application errors bubble up and this mapper turns
    them into proper status codes.
    """
    app.add_exception_handler(FieldError, _field_error_handler)
    app.add_exception_handler(EntityNotFoundError, _entity_not_found_handler)
