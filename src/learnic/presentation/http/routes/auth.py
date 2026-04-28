from http import HTTPStatus
from typing import Final

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Request, Response, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

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
from learnic.entities.user.constants import (
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
    PATRONYMIC_MAX_LEN,
)
from learnic.infrastructure.configs import SecurityConfig
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
    refresh_cookie_scheme,
    signup_session_cookie_scheme,
)
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

_ACCESS_SECURITY: Final = [Depends(access_cookie_scheme)]
_REFRESH_SECURITY: Final = [Depends(refresh_cookie_scheme)]
_SIGNUP_SESSION_SECURITY: Final = [Depends(signup_session_cookie_scheme)]


class RegisterSchema(BaseModel):
    """Body for `POST /auth/register`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "ada@example.com",
                    "password": "correct horse battery staple",  # noqa: S105  # nosec B105
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "patronymic": None,
                },
            ],
        },
    )

    email: str = Field(
        description=(
            "Login email. Must be a valid address; not unique-checked "
            "client-side, but the server returns 409 "
            "`EmailAlreadyRegistered` when taken. "
            f"Max length is {EMAIL_MAX_LEN} characters "
            "(`EMAIL_MAX_LEN`)."
        ),
        min_length=1,
        max_length=EMAIL_MAX_LEN,
        examples=["ada@example.com"],
    )
    password: str = Field(
        description=(
            f"Plain-text password. Length must be in "
            f"`[{PASSWORD_MIN_LEN}, {PASSWORD_MAX_LEN}]` "
            "(`PASSWORD_MIN_LEN`/`PASSWORD_MAX_LEN`). The server "
            "applies additional strength rules and returns 422 "
            "`WeakPasswordError` when violated."
        ),
        min_length=PASSWORD_MIN_LEN,
        max_length=PASSWORD_MAX_LEN,
        examples=["correct horse battery staple"],
    )
    first_name: str = Field(
        description=(
            "User's given name. Required, non-empty after trimming. "
            f"Max length is {FIRST_NAME_MAX_LEN} characters "
            "(`FIRST_NAME_MAX_LEN`)."
        ),
        min_length=1,
        max_length=FIRST_NAME_MAX_LEN,
        examples=["Ada"],
    )
    last_name: str = Field(
        description=(
            "User's family name. Required, non-empty after trimming. "
            f"Max length is {LAST_NAME_MAX_LEN} characters "
            "(`LAST_NAME_MAX_LEN`)."
        ),
        min_length=1,
        max_length=LAST_NAME_MAX_LEN,
        examples=["Lovelace"],
    )
    patronymic: str | None = Field(
        default=None,
        description=(
            "Optional middle/patronymic name. Omit or pass `null` "
            "when not applicable. "
            f"Max length is {PATRONYMIC_MAX_LEN} characters "
            "(`PATRONYMIC_MAX_LEN`)."
        ),
        max_length=PATRONYMIC_MAX_LEN,
        examples=[None, "Augusta"],
    )


class LoginSchema(BaseModel):
    """Body for `POST /auth/login`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "ada@example.com",
                    "password": "correct horse battery staple",  # noqa: S105  # nosec B105
                },
            ],
        },
    )

    email: str = Field(
        description="Login email of an existing, verified user.",
        min_length=1,
        max_length=EMAIL_MAX_LEN,
        examples=["ada@example.com"],
    )
    password: str = Field(
        description="Plain-text password to verify against the stored hash.",
        min_length=PASSWORD_MIN_LEN,
        max_length=PASSWORD_MAX_LEN,
        examples=["correct horse battery staple"],
    )


class VerifyEmailSchema(BaseModel):
    """Body for `POST /auth/email-verification/verify`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"token": "8f3...d2"}],  # noqa: S105  # nosec B105
        },
    )

    token: str = Field(
        description=(
            "Single-use verification token delivered by email. The "
            "token is opaque to clients; copy it verbatim from the "
            "verification link's query string."
        ),
        min_length=1,
        examples=["8f3...d2"],
    )


class RequestPasswordResetSchema(BaseModel):
    """Body for `POST /auth/password-reset/request`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "ada@example.com"}]},
    )

    email: str = Field(
        description=(
            "Address to send the reset link to. The endpoint always "
            "returns 204 — existence of an account is intentionally "
            "not leaked through the response."
        ),
        min_length=1,
        max_length=EMAIL_MAX_LEN,
        examples=["ada@example.com"],
    )


class ResetPasswordSchema(BaseModel):
    """Body for `POST /auth/password-reset/confirm`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "token": "8f3...d2",  # noqa: S105  # nosec B105
                    "new_password": "correct horse battery staple",  # noqa: S105  # nosec B105
                },
            ],
        },
    )

    token: str = Field(
        description=(
            "Single-use reset token delivered by email. Opaque to "
            "clients; copy verbatim from the reset link."
        ),
        min_length=1,
        examples=["8f3...d2"],
    )
    new_password: str = Field(
        description=(
            f"Replacement password. Length must be in "
            f"`[{PASSWORD_MIN_LEN}, {PASSWORD_MAX_LEN}]` "
            "(`PASSWORD_MIN_LEN`/`PASSWORD_MAX_LEN`). Re-validated "
            "against strength rules; 422 `WeakPasswordError` if it "
            "fails."
        ),
        min_length=PASSWORD_MIN_LEN,
        max_length=PASSWORD_MAX_LEN,
        examples=["correct horse battery staple"],
    )


@router.post(
    "/register",
    summary="Register a new user account",
    operation_id="register",
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
        ``201 Created`` with an empty body. The ``signup_session``
        cookie tells the SPA it is in the "wait for verification"
        state; poll ``GET /auth/email-verification/wait`` from that
        tab to auto-login once the user clicks the email link.

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
    summary="Log in with email and password",
    operation_id="login",
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
        ``204 No Content`` with `Set-Cookie` headers installing
        `accessCookie` and `refreshCookie`. The SPA must subsequently
        send requests with `credentials: "include"`.

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
    summary="Rotate the refresh cookie for fresh tokens",
    operation_id="refreshTokens",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_REFRESH_SECURITY,
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
        ``204 No Content`` with rotated `accessCookie` and
        `refreshCookie`.

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
    summary="Log out the current device",
    operation_id="logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[*_ACCESS_SECURITY, *_REFRESH_SECURITY],
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
        ``204 No Content`` after cleanup. `Set-Cookie` headers clear
        `accessCookie` and `refreshCookie`.

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
    summary="Revoke every session for the current user",
    operation_id="logoutAll",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_ACCESS_SECURITY,
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
        ``204 No Content`` after cleanup. Other devices keep their
        cookies but their next refresh attempt will fail.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(LogoutAllCommand(user_id=ctx.user_id))
    clear_auth_cookies(response, cfg)


@router.post(
    "/email-verification/verify",
    summary="Verify a user's email with the link token",
    operation_id="verifyEmail",
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
        ``204 No Content`` on success. The original registration tab
        (which holds the `signupSessionCookie`) will pick this up via
        `GET /auth/email-verification/wait` and be logged in.

    Raises:
        InvalidTokenError: Token unknown, expired, already consumed,
            or issued for a different purpose; HTTP 401.
    """
    await interactor.run(VerifyEmailCommand(token=payload.token))


@router.get(
    "/email-verification/wait",
    summary="Long-poll for the registration tab to auto-login",
    operation_id="waitForEmailVerification",
    dependencies=_SIGNUP_SESSION_SECURITY,
    responses={
        status.HTTP_200_OK: {
            "description": (
                "Email is now verified. Auth cookies are set; the "
                "`signup_session` cookie is cleared. Body is empty."
            ),
        },
        status.HTTP_204_NO_CONTENT: {
            "description": (
                "Still waiting for the user to click the verification link. Poll again."
            ),
        },
    },
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
    summary="Request a password-reset email",
    operation_id="requestPasswordReset",
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
    summary="Confirm a password reset with the link token",
    operation_id="confirmPasswordReset",
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
        ``204 No Content`` on success. Existing sessions are revoked;
        the user must log in again.

    Raises:
        InvalidTokenError: Token unknown/expired/used; HTTP 401.
        FieldError: ``new_password`` violates the password invariants;
            HTTP 422.
    """
    await interactor.run(
        ResetPasswordCommand(
            token=payload.token,
            new_password=payload.new_password,
        )
    )


@router.get(
    "/me",
    summary="Get the currently authenticated user's profile",
    operation_id="getMyProfile",
    response_model=UserSchema,
    dependencies=_ACCESS_SECURITY,
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
