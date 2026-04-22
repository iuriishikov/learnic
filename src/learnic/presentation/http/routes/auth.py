from http import HTTPStatus
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response, status
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
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.application.queries.user.get import (
    GetUserQuery,
    GetUserQueryHandler,
)
from learnic.infrastructure.configs import SecurityConfig
from learnic.presentation.http.common.auth_deps import authenticate
from learnic.presentation.http.common.cookies import (
    REFRESH_COOKIE,
    SIGNUP_SESSION_COOKIE,
    clear_auth_cookies,
    clear_signup_session_cookie,
    set_auth_cookies,
    set_signup_session_cookie,
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    route_class=DishkaRoute,
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


class UserSchema(BaseModel):
    oid: UUID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None
    avatar_url: str | None
    cover_url: str | None


@router.post("/register", status_code=status.HTTP_201_CREATED)
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
        FieldError: One of the value-object invariants was violated
            (invalid email, weak password, empty/too long name);
            mapped to HTTP 422.
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


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
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
        InvalidCredentialsError: No user or wrong password; mapped to
            HTTP 401.
        EmailNotVerifiedError: User has not confirmed the email yet;
            mapped to HTTP 403.
    """
    pair = await interactor.run(
        LoginCommand(email=payload.email, password=payload.password),
    )
    set_auth_cookies(response, pair, cfg)


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
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
            (reuse also revokes the entire family); mapped to HTTP 401.
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise InvalidTokenError
    pair = await interactor.run(RefreshCommand(refresh_token=raw))
    set_auth_cookies(response, pair, cfg)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    interactor: FromDishka[LogoutCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Revoke this device's refresh family and deny the current access jti.

    Args:
        request: Source of the ``refresh_token`` and ``access_token``
            cookies.
        response: Used to clear auth cookies.
        interactor: Injected logout command handler.
        access_tokens: Injected access-token service for cookie decode.
        denylist: Injected access-token denylist.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` after cleanup.

    Raises:
        InvalidTokenError: No valid access cookie; mapped to HTTP 401.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    await interactor.run(
        LogoutCommand(
            refresh_token=request.cookies.get(REFRESH_COOKIE),
            access_jti=ctx.jti,
            access_expires_at=ctx.expires_at,
        )
    )
    clear_auth_cookies(response, cfg)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request,
    response: Response,
    interactor: FromDishka[LogoutAllCommandHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Revoke every refresh session for the current user.

    Args:
        request: Source of the access cookie used to authenticate.
        response: Used to clear this device's auth cookies.
        interactor: Injected logout-all command handler.
        access_tokens: Injected access-token service for cookie decode.
        denylist: Injected access-token denylist.
        cfg: Injected security config driving cookie flags.

    Returns:
        ``204 No Content`` after cleanup.

    Raises:
        InvalidTokenError: No valid access cookie; mapped to HTTP 401.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    await interactor.run(LogoutAllCommand(user_id=ctx.user_id))
    clear_auth_cookies(response, cfg)


@router.post("/email-verification/verify", status_code=status.HTTP_204_NO_CONTENT)
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
            or issued for a different purpose; mapped to HTTP 401.
    """
    await interactor.run(VerifyEmailCommand(token=payload.token))


@router.get("/email-verification/wait")
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
          ``signup_session`` cookie cleared. Body is empty; the status
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


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
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
    """
    await interactor.run(RequestPasswordResetCommand(email=payload.email))


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
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


@router.get("/me", response_model=UserSchema)
async def me(
    request: Request,
    interactor: FromDishka[GetUserQueryHandler],
    access_tokens: FromDishka[AccessTokenService],
    denylist: FromDishka[TokenDenylist],
) -> UserSchema:
    """Return the currently authenticated user's profile.

    Args:
        request: Source of the access cookie used to authenticate.
        interactor: Injected get-user query handler.
        access_tokens: Injected access-token service for cookie decode.
        denylist: Injected access-token denylist.

    Returns:
        ``UserSchema`` with the user's public profile fields.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
        EntityNotFoundError: User row vanished (e.g. deleted mid-session);
            HTTP 404.
    """
    ctx = await authenticate(request, access_tokens, denylist)
    view = await interactor.run(GetUserQuery(oid=ctx.user_id))
    return UserSchema(
        oid=view.oid,
        email=view.email,
        first_name=view.first_name,
        last_name=view.last_name,
        patronymic=view.patronymic,
        avatar_url=view.avatar_url,
        cover_url=view.cover_url,
    )
