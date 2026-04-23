from http import HTTPStatus

from dishka.integrations.fastapi import FromDishka
from fastapi import Request, Response, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel

from learnic.application.commands.auth.login import (
    LoginCommand,
    LoginCommandHandler,
)
from learnic.application.commands.auth.logout import (
    LogoutCommand,
    LogoutCommandHandler,
)
from learnic.application.commands.auth.logout_all import (
    LogoutAllCommand,
    LogoutAllCommandHandler,
)
from learnic.application.commands.auth.refresh import (
    RefreshCommand,
    RefreshCommandHandler,
)
from learnic.application.commands.auth.register import (
    RegisterCommand,
    RegisterCommandHandler,
)
from learnic.application.commands.auth.request_password_reset import (
    RequestPasswordResetCommand,
    RequestPasswordResetCommandHandler,
)
from learnic.application.commands.auth.reset_password import (
    ResetPasswordCommand,
    ResetPasswordCommandHandler,
)
from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)
from learnic.application.commands.auth.verify_wait import (
    VerifyWaitCommand,
    VerifyWaitCommandHandler,
)
from learnic.application.common.errors import (
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from learnic.application.queries.user.get import (
    GetUserQuery,
    GetUserQueryHandler,
)
from learnic.entities.common.errors import FieldError
from learnic.infrastructure.configs import SecurityConfig
from learnic.presentation.http.common.auth_deps import Authenticator
from learnic.presentation.http.common.cookies import (
    REFRESH_COOKIE,
    SIGNUP_SESSION_COOKIE,
    clear_auth_cookies,
    clear_signup_session_cookie,
    set_auth_cookies,
    set_signup_session_cookie,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    EMAIL_ALREADY_REGISTERED_RULE,
    EMAIL_NOT_VERIFIED_RULE,
    FIELD_ERROR_RULE,
    INVALID_CREDENTIALS_RULE,
    INVALID_TOKEN_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import UserSchema

router = ErrorAwareRouter(
    prefix="/auth",
    tags=["Auth"],
    route_class=DishkaErrorAwareRoute,
)


class RegisterSchema(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    patronymic: str | None = None


class LoginSchema(BaseModel):
    email: str
    password: str


class VerifyEmailSchema(BaseModel):
    token: str


class RequestPasswordResetSchema(BaseModel):
    email: str


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    error_map={
        FieldError: FIELD_ERROR_RULE,
        EmailAlreadyRegisteredError: EMAIL_ALREADY_REGISTERED_RULE,
    },
)
async def register(
    payload: RegisterSchema,
    response: Response,
    interactor: FromDishka[RegisterCommandHandler],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Register a new user and mail a verification link.

    Args:
        payload: Email, password, and name fields; validated by Pydantic
            at the HTTP boundary and wrapped into domain value objects
            by the handler.
        response: Used to install the ``signup_session`` cookie so that
            the registration tab can auto-login once the user verifies.
        interactor: Injected register command handler.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``201 Created`` with an empty body; the ``signup_session`` cookie
        tells the SPA it is in the "wait for verification" state.

    Raises:
        FieldError: VO invariant violated (invalid email, weak password,
            empty/too long name); mapped to HTTP 422.
        EmailAlreadyRegisteredError: Another user already owns this
            email; mapped to HTTP 409.
    """
    result = await interactor.run(
        RegisterCommand(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            patronymic=payload.patronymic,
        ),
    )
    set_signup_session_cookie(response, result.signup_session_token, cfg)


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={
        FieldError: FIELD_ERROR_RULE,
        InvalidCredentialsError: INVALID_CREDENTIALS_RULE,
        EmailNotVerifiedError: EMAIL_NOT_VERIFIED_RULE,
    },
)
async def login(
    payload: LoginSchema,
    response: Response,
    interactor: FromDishka[LoginCommandHandler],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Authenticate by email and password; set auth cookies.

    Args:
        payload: ``email`` + ``password`` pair.
        response: Used to set ``access_token`` and ``refresh_token``
            cookies.
        interactor: Injected login command handler.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` with auth cookies set.

    Raises:
        InvalidCredentialsError: No user or wrong password; HTTP 401.
        EmailNotVerifiedError: Email not confirmed; HTTP 403.
        FieldError: VO violated during password/email parse; HTTP 422.
    """
    pair = await interactor.run(
        LoginCommand(email=payload.email, password=payload.password),
    )
    set_auth_cookies(response, pair, cfg)


@router.post(
    "/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def refresh(
    request: Request,
    response: Response,
    interactor: FromDishka[RefreshCommandHandler],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Rotate the refresh cookie for a fresh access/refresh pair.

    Args:
        request: Source of the incoming ``refresh_token`` cookie.
        response: Used to install the rotated cookies.
        interactor: Injected refresh command handler.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` with rotated cookies.

    Raises:
        InvalidTokenError: Cookie missing, expired, revoked, or reused
            (reuse also revokes the entire family); HTTP 401.
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise InvalidTokenError
    pair = await interactor.run(RefreshCommand(refresh_token=raw))
    set_auth_cookies(response, pair, cfg)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def logout(
    request: Request,
    response: Response,
    interactor: FromDishka[LogoutCommandHandler],
    auth: FromDishka[Authenticator],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Revoke this device's refresh family and deny the current access jti.

    Args:
        request: Source of ``refresh_token`` and ``access_token`` cookies.
        response: Used to clear auth cookies.
        interactor: Injected logout command handler.
        auth: Injected authenticator that validates the access cookie.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` after cleanup.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        LogoutCommand(
            refresh_token=request.cookies.get(REFRESH_COOKIE),
            access_jti=ctx.jti,
            access_expires_at=ctx.expires_at,
        )
    )
    clear_auth_cookies(response, cfg)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def logout_all(
    request: Request,
    response: Response,
    interactor: FromDishka[LogoutAllCommandHandler],
    auth: FromDishka[Authenticator],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Revoke every refresh session for the current user.

    Args:
        request: Source of the access cookie used to authenticate.
        response: Used to clear this device's auth cookies.
        interactor: Injected logout-all command handler.
        auth: Injected authenticator that validates the access cookie.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` after cleanup.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(LogoutAllCommand(user_id=ctx.user_id))
    clear_auth_cookies(response, cfg)


@router.post(
    "/email-verification/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def email_verification_verify(
    payload: VerifyEmailSchema,
    interactor: FromDishka[VerifyEmailCommandHandler],
) -> None:
    """Consume a verification token emailed to the user.

    Args:
        payload: Carries the raw single-use token from the email link.
        interactor: Injected verify-email command handler.

    Returns:
        ``204 No Content`` on success.

    Raises:
        InvalidTokenError: Token unknown, expired, already consumed,
            or issued for a different purpose; HTTP 401.
    """
    await interactor.run(VerifyEmailCommand(token=payload.token))


@router.get(
    "/email-verification/wait",
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def email_verification_wait(
    request: Request,
    interactor: FromDishka[VerifyWaitCommandHandler],
    cfg: FromDishka[SecurityConfig],
) -> Response:
    """Poll-endpoint for the registration tab to auto-login on verify.

    Behavior:
        - ``signup_session`` cookie missing or expired: 401.
        - Email not yet verified: 204 (keep polling).
        - Email verified: 200 with auth cookies set and the
          ``signup_session`` cookie cleared. Body empty; the status
          code alone tells the SPA to transition.

    Args:
        request: Source of the ``signup_session`` cookie.
        interactor: Injected verify-wait command handler.
        cfg: Injected security config driving cookie flags.

    Returns:
        204 while waiting; 200 with auth cookies once ready.

    Raises:
        InvalidTokenError: ``signup_session`` missing/expired; HTTP 401.
    """
    raw = request.cookies.get(SIGNUP_SESSION_COOKIE)
    if not raw:
        raise InvalidTokenError
    result = await interactor.run(VerifyWaitCommand(signup_session_token=raw))
    if not result.ready or result.token_pair is None:
        return Response(status_code=HTTPStatus.NO_CONTENT)
    response = Response(status_code=HTTPStatus.OK)
    set_auth_cookies(response, result.token_pair, cfg)
    clear_signup_session_cookie(response, cfg)
    return response


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={FieldError: FIELD_ERROR_RULE},
)
async def password_reset_request(
    payload: RequestPasswordResetSchema,
    interactor: FromDishka[RequestPasswordResetCommandHandler],
) -> None:
    """Email a password-reset link if ``email`` is registered.

    Always returns 204 regardless of whether the email exists — existence
    of an account is intentionally not leaked through this endpoint.

    Args:
        payload: Address to send the reset link to.
        interactor: Injected request-password-reset command handler.

    Returns:
        ``204 No Content``.

    Raises:
        FieldError: Email VO invariant violated (empty / too long);
            HTTP 422.
    """
    await interactor.run(RequestPasswordResetCommand(email=payload.email))


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    error_map={
        FieldError: FIELD_ERROR_RULE,
        InvalidTokenError: INVALID_TOKEN_RULE,
    },
)
async def password_reset_confirm(
    payload: ResetPasswordSchema,
    interactor: FromDishka[ResetPasswordCommandHandler],
) -> None:
    """Consume a reset token, set a new password, revoke all sessions.

    Args:
        payload: Token plus the new password (validated by the
            ``RawPassword`` VO inside the handler).
        interactor: Injected reset-password command handler.

    Returns:
        ``204 No Content`` on success.

    Raises:
        InvalidTokenError: Token unknown/expired/used; HTTP 401.
        FieldError: ``new_password`` violates the password invariants;
            HTTP 422.
    """
    await interactor.run(
        ResetPasswordCommand(token=payload.token, new_password=payload.new_password)
    )


@router.get(
    "/me",
    response_model=UserSchema,
    error_map=AUTHENTICATED_MAP,
)
async def me(
    request: Request,
    interactor: FromDishka[GetUserQueryHandler],
    auth: FromDishka[Authenticator],
) -> UserSchema:
    """Return the currently authenticated user's profile.

    Args:
        request: Source of the access cookie used to authenticate.
        interactor: Injected get-user query handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``UserSchema`` with the user's public profile fields.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
        EntityNotFoundError: User row vanished; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(GetUserQuery(oid=ctx.user_id))
    return UserSchema.from_view(view)
