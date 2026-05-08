from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter

from learnic.application.commands.product_qa.change_answer import (
    ChangeProductQAAnswerCommand,
    ChangeProductQAAnswerCommandHandler,
)
from learnic.application.commands.product_qa.change_question import (
    ChangeProductQAQuestionCommand,
    ChangeProductQAQuestionCommandHandler,
)
from learnic.application.commands.product_qa.delete import (
    DeleteProductQACommand,
    DeleteProductQACommandHandler,
)
from learnic.application.commands.product_qa.reorder import (
    ReorderProductQACommand,
    ReorderProductQACommandHandler,
)
from learnic.entities.product.ids import ProductQAID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.routes.product import (
    ChangeProductQAAnswerSchema,
    ChangeProductQAQuestionSchema,
    ReorderProductQASchema,
)

router = ErrorAwareRouter(
    prefix="/products/{product_id}/qa",
    tags=["Products"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Parent product UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_QA_ID_PATH: Final = Path(
    description="Target Q&A entry UUID.",
    examples=["5b2c8a90-6fcd-4d2c-9d11-9d4f0a44b6c8"],
)


@router.patch(
    "/{qa_id}/question",
    summary="Change a Q&A entry's question",
    operation_id="changeProductQAQuestion",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_question(
    request: Request,
    payload: ChangeProductQAQuestionSchema,
    interactor: FromDishka[ChangeProductQAQuestionCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,  # noqa: ARG001
    qa_id: UUID = _QA_ID_PATH,
) -> None:
    """Replace the question of a Q&A entry.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new question>"}``.
        interactor: Injected change-question command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Parent product's UUID, parsed from the URL path.
        qa_id: Target Q&A entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the parent product's
            author; HTTP 403.
        EntityNotFoundError: No Q&A or product with the given id;
            HTTP 404.
        FieldError: ``QAQuestion`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductQAQuestionCommand(
            actor_id=ctx.user_id,
            qa_id=ProductQAID(qa_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{qa_id}/answer",
    summary="Change a Q&A entry's answer",
    operation_id="changeProductQAAnswer",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_answer(
    request: Request,
    payload: ChangeProductQAAnswerSchema,
    interactor: FromDishka[ChangeProductQAAnswerCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,  # noqa: ARG001
    qa_id: UUID = _QA_ID_PATH,
) -> None:
    """Replace the answer of a Q&A entry.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new answer>"}``.
        interactor: Injected change-answer command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Parent product's UUID, parsed from the URL path.
        qa_id: Target Q&A entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the parent product's
            author; HTTP 403.
        EntityNotFoundError: No Q&A or product with the given id;
            HTTP 404.
        FieldError: ``QAAnswer`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeProductQAAnswerCommand(
            actor_id=ctx.user_id,
            qa_id=ProductQAID(qa_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{qa_id}/position",
    summary="Reorder a Q&A entry within its product",
    operation_id="reorderProductQA",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def reorder(
    request: Request,
    payload: ReorderProductQASchema,
    interactor: FromDishka[ReorderProductQACommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,  # noqa: ARG001
    qa_id: UUID = _QA_ID_PATH,
) -> None:
    """Update the sort position of a Q&A entry.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"position": <int>}``, `>= 0`.
        interactor: Injected reorder command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Parent product's UUID, parsed from the URL path.
        qa_id: Target Q&A entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the parent product's
            author; HTTP 403.
        EntityNotFoundError: No Q&A or product with the given id;
            HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ReorderProductQACommand(
            actor_id=ctx.user_id,
            qa_id=ProductQAID(qa_id),
            position=payload.position,
        ),
    )


@router.delete(
    "/{qa_id}",
    summary="Delete a Q&A entry",
    operation_id="deleteProductQA",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_qa(
    request: Request,
    interactor: FromDishka[DeleteProductQACommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,  # noqa: ARG001
    qa_id: UUID = _QA_ID_PATH,
) -> None:
    """Delete a Q&A entry.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected delete command handler.
        auth: Injected authenticator that validates the access cookie.
        product_id: Parent product's UUID, parsed from the URL path.
        qa_id: Target Q&A entry's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the parent product's
            author; HTTP 403.
        EntityNotFoundError: No Q&A or product with the given id;
            HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteProductQACommand(
            actor_id=ctx.user_id,
            qa_id=ProductQAID(qa_id),
        ),
    )
