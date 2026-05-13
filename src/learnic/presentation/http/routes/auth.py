import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Final

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, Response, status
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
from learnic.application.commands.auth.resend_verification import (
    ResendVerificationCommand,
    ResendVerificationCommandHandler,
)
from learnic.application.commands.auth.reset_password import (
    ResetPasswordCommand,
    ResetPasswordCommandHandler,
)
from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)
from learnic.application.commands.auth.verify_token import (
    VerifyTokenCommand,
    VerifyTokenCommandHandler,
)
from learnic.application.commands.auth.verify_wait import (
    VerifyWaitCommand,
    VerifyWaitCommandHandler,
)
from learnic.application.commands.session.revoke import (
    RevokeSessionCommand,
    RevokeSessionCommandHandler,
)
from learnic.application.common.errors import (
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    EntityNotFoundError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from learnic.application.common.persistence.session import SessionView
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.queries.auth.token_status import (
    GetTokenStatusQuery,
    GetTokenStatusQueryHandler,
)
from learnic.application.queries.session.list_my import (
    ListMySessionsQuery,
    ListMySessionsQueryHandler,
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
from learnic.presentation.http.common.device import device_from_request
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    EMAIL_ALREADY_REGISTERED_RULE,
    EMAIL_NOT_VERIFIED_RULE,
    ENTITY_NOT_FOUND_RULE,
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


class VerifyTokenSchema(BaseModel):
    """Body for `POST /auth/verify-token`.

    Used by the unified ``/confirm/<purpose>`` SPA page to consume any
    routable single-token email confirmation in one call. The handler
    looks up ``purpose`` from the token itself; the SPA does not need
    to declare it.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"token": "8f3...d2"}],  # noqa: S105  # nosec B105
        },
    )

    token: str = Field(
        description=(
            "Single-use token delivered by email. Opaque to clients; "
            "copy verbatim from the confirmation link's query string."
        ),
        min_length=1,
        examples=["8f3...d2"],
    )


class VerifyTokenResponse(BaseModel):
    """Response body for `POST /auth/verify-token`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"purpose": "verify"}]},
    )

    purpose: str = Field(
        description=(
            "Purpose the token was issued for. Mirrors "
            "`EmailTokenPurpose` values (`verify`, ...). The SPA may "
            "use this to pick localized success copy or to choose a "
            "post-confirm redirect."
        ),
        examples=["verify"],
    )


class TokenStatusSchema(BaseModel):
    """Body for `POST /auth/token-status`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"token": "8f3...d2"}],  # noqa: S105  # nosec B105
        },
    )

    token: str = Field(
        description=(
            "Single-use token delivered by email. The endpoint peeks "
            "at the token without consuming, so the SPA can render a "
            "form (e.g. password-reset) only when the link is still "
            "live."
        ),
        min_length=1,
        examples=["8f3...d2"],
    )


class TokenStatusResponse(BaseModel):
    """Response body for `POST /auth/token-status`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"purpose": "reset"}]},
    )

    purpose: str = Field(
        description=(
            "Purpose the token was issued for. Mirrors `EmailTokenPurpose` values."
        ),
        examples=["verify", "reset"],
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
    request: Request,
    response: Response,
    interactor: FromDishka[LoginCommandHandler],
    cfg: FromDishka[SecurityConfig],
) -> None:
    """Authenticate by email and password; set auth cookies.

    Args:
        payload: ``email`` + ``password`` pair.
        request: Source of device metadata (IP, ``User-Agent``) recorded
            on the new refresh-token row so the user can later see and
            revoke this session under `GET /auth/sessions`.
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
        LoginCommand(
            email=payload.email,
            password=payload.password,
            device=device_from_request(request),
        ),
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
    pair = await interactor.run(
        RefreshCommand(
            refresh_token=raw,
            device=device_from_request(request),
        ),
    )
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
    """Revoke this device's refresh family and deny it instantly.

    The revoked ``family_id`` is added to the family denylist for one
    access-TTL window so the in-flight access cookie (and any tabs
    that refreshed off the same family) is rejected on the next
    request, not after the access JWT's natural ``exp``.

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
            access_family_id=ctx.family_id,
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
    result = await interactor.run(
        VerifyWaitCommand(
            signup_session_token=raw,
            device=device_from_request(request),
        ),
    )
    if not result.ready or result.token_pair is None:
        return Response(status_code=HTTPStatus.NO_CONTENT)
    response = Response(status_code=HTTPStatus.OK)
    set_auth_cookies(response, result.token_pair, cfg)
    clear_signup_session_cookie(response, cfg)
    return response


@router.post(
    "/email-verification/resend",
    summary="Re-issue the verification email for the registration tab",
    operation_id="resendVerificationEmail",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_SIGNUP_SESSION_SECURITY,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def email_verification_resend(
    request: Request,
    interactor: FromDishka[ResendVerificationCommandHandler],
) -> None:
    """Re-issue and re-send the verification email.

    Identifies the pending user via the ``signup_session`` cookie set
    on registration. Issuing a new VERIFY token implicitly invalidates
    any previously-active VERIFY token for the same user, so older
    links stop working after this call — exactly what resend should do.

    Args:
        request: Source of the ``signup_session`` cookie.
        interactor: Injected resend-verification command handler.

    Returns:
        ``204 No Content`` on success or when the user is already
        verified (the email is cosmetic at that point and we don't
        leak verification state through error shape).

    Raises:
        InvalidTokenError: ``signup_session`` missing or expired;
            HTTP 401.
    """
    raw = request.cookies.get(SIGNUP_SESSION_COOKIE)
    if not raw:
        raise InvalidTokenError
    await interactor.run(
        ResendVerificationCommand(signup_session_token=raw),
    )


@router.post(
    "/verify-token",
    summary="Confirm any single-token email action in one call",
    operation_id="verifyToken",
    response_model=VerifyTokenResponse,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def verify_token(
    payload: VerifyTokenSchema,
    interactor: FromDishka[VerifyTokenCommandHandler],
) -> VerifyTokenResponse:
    """Consume an email-confirmation token through the unified path.

    Looks up the token's purpose and delegates to the matching
    specialized command handler. The SPA's ``/confirm/<purpose>``
    page hits this endpoint so adding a new email-confirmed action
    requires no frontend deploy: ship the new purpose + handler on
    the backend, and the generic confirm page picks it up via the
    purpose echoed back in the response.

    Purposes routed here are listed in
    ``application.commands.auth.verify_token._UNIFIED_PURPOSES``.
    Purposes that need extra request fields (e.g. ``RESET`` needs a
    new password) keep their own routes; this endpoint rejects them
    with 401 to keep the response shape uniform with unknown tokens.

    Args:
        payload: Carries the raw single-use token from the email link.
        interactor: Injected unified verify-token command handler.

    Returns:
        ``200 OK`` with ``{"purpose": "..."}`` describing the consumed
        token. The SPA may use ``purpose`` to pick localized copy.

    Raises:
        InvalidTokenError: Token unknown / expired / already consumed,
            or its purpose is not routable through this endpoint;
            HTTP 401.
    """
    result = await interactor.run(VerifyTokenCommand(token=payload.token))
    return VerifyTokenResponse(purpose=result.purpose)


@router.post(
    "/token-status",
    summary="Peek at an email-confirmation token without consuming",
    operation_id="getTokenStatus",
    response_model=TokenStatusResponse,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def token_status(
    payload: TokenStatusSchema,
    interactor: FromDishka[GetTokenStatusQueryHandler],
) -> TokenStatusResponse:
    """Validate an email-confirmation token without consuming it.

    Used by the SPA to gate form-based confirm screens (e.g.
    ``/reset-password``) on a still-live link, and by the unified
    ``/confirm/<purpose>`` page when it wants to pick localized copy
    before the consume call.

    Always POST: the token rides in the body so it cannot leak through
    access logs / Referer headers / browser history.

    Args:
        payload: Token to peek at.
        interactor: Injected token-status query handler.

    Returns:
        ``200 OK`` with ``{"purpose": "..."}`` if the token is live.

    Raises:
        InvalidTokenError: Token unknown / expired / already consumed;
            HTTP 401.
    """
    view = await interactor.run(GetTokenStatusQuery(token=payload.token))
    return TokenStatusResponse(purpose=view.purpose)


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


class SessionSchema(BaseModel):
    """One active refresh-token session for the authenticated user."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "11111111-2222-3333-4444-555555555555",
                    "created_at": "2026-05-01T08:00:00+00:00",
                    "last_used_at": "2026-05-08T07:42:11+00:00",
                    "expires_at": "2026-05-31T08:00:00+00:00",
                    "ip_address": "203.0.113.42",
                    "user_agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/17.5 Safari/605.1.15"
                    ),
                    "device_label": "Safari on macOS",
                    "is_current": True,
                },
            ],
        },
    )

    id: uuid.UUID = Field(
        description=(
            "Public session id. Equals the refresh-token family id — "
            "the SPA passes it to `DELETE /auth/sessions/{id}` to "
            "remotely sign out that specific device."
        ),
    )
    created_at: datetime = Field(
        description=(
            "When the session was first opened (i.e. when the user "
            "logged in on this device). UTC, ISO 8601."
        ),
    )
    last_used_at: datetime = Field(
        description=(
            "When the session was last refreshed (rotation moment). "
            "Use this as the user-facing 'last activity' timestamp. "
            "UTC, ISO 8601."
        ),
    )
    expires_at: datetime = Field(
        description=(
            "When the active refresh cookie naturally dies if no "
            "refresh occurs first. UTC, ISO 8601."
        ),
    )
    ip_address: str | None = Field(
        default=None,
        description=(
            "Best-known originating IP for this session. May be "
            "`null` for legacy sessions that pre-date the device-"
            "metadata feature, or when the request had no usable "
            "client address."
        ),
    )
    user_agent: str | None = Field(
        default=None,
        description=(
            "Raw `User-Agent` header captured at the most recent "
            "refresh, truncated to 512 chars. May be `null`. The SPA "
            "should prefer `device_label` for display."
        ),
    )
    device_label: str | None = Field(
        default=None,
        description=(
            "Short human-readable label parsed from `user_agent` "
            '(e.g. `"Chrome on Windows"`). Best-effort; may be '
            "`null` when no heuristic matched."
        ),
    )
    is_current: bool = Field(
        description=(
            "`true` when this session matches the refresh cookie sent "
            "with the request. The SPA can highlight it as 'this "
            "device' and warn before letting the user revoke it."
        ),
    )

    @classmethod
    def from_view(cls, view: SessionView, *, is_current: bool) -> "SessionSchema":
        return cls(
            id=view.family_id,
            created_at=view.created_at,
            last_used_at=view.last_used_at,
            expires_at=view.expires_at,
            ip_address=view.ip_address,
            user_agent=view.user_agent,
            device_label=view.device_label,
            is_current=is_current,
        )


@router.get(
    "/sessions",
    summary="List the current user's active sessions",
    operation_id="listMySessions",
    response_model=list[SessionSchema],
    dependencies=_ACCESS_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def list_sessions(
    request: Request,
    interactor: FromDishka[ListMySessionsQueryHandler],
    refresh_store: FromDishka[RefreshTokenStore],
    auth: FromDishka[Authenticator],
) -> list[SessionSchema]:
    """List every active refresh-token session for the caller.

    Each entry carries the device/location metadata captured at issue
    or last rotation: IP, raw `User-Agent`, a short parsed
    `device_label`, plus the `created_at` / `last_used_at` /
    `expires_at` timestamps. The session that matches the caller's
    own `refreshCookie` (when present) is flagged with
    `is_current = true` so the SPA can render it as 'this device'.

    Args:
        request: Source of the access cookie (auth) and — when
            available — the refresh cookie used to flag the current
            session.
        interactor: Injected list-my-sessions query handler.
        refresh_store: Used to resolve the caller's refresh cookie to
            the family id powering the `is_current` flag.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        Active sessions ordered by `last_used_at` descending.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(ListMySessionsQuery(user_id=ctx.user_id))

    current_family_id: uuid.UUID | None = None
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        record = await refresh_store.resolve(raw_refresh)
        if record is not None and record.user_id == ctx.user_id:
            current_family_id = record.family_id

    return [
        SessionSchema.from_view(view, is_current=view.family_id == current_family_id)
        for view in views
    ]


_SESSION_REVOKE_MAP: Final = AUTHENTICATED_MAP | {
    EntityNotFoundError: ENTITY_NOT_FOUND_RULE,
}


@router.delete(
    "/sessions/{session_id}",
    summary="Revoke a specific session of the current user",
    operation_id="revokeMySession",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_ACCESS_SECURITY,
    error_map=_SESSION_REVOKE_MAP,
)
async def revoke_session(
    request: Request,
    response: Response,
    interactor: FromDishka[RevokeSessionCommandHandler],
    refresh_store: FromDishka[RefreshTokenStore],
    auth: FromDishka[Authenticator],
    cfg: FromDishka[SecurityConfig],
    session_id: uuid.UUID = Path(
        description=(
            "Public session id (refresh-token family id) returned by "
            "`GET /auth/sessions`."
        ),
    ),
) -> None:
    """Revoke one of the caller's active sessions.

    Used to remotely sign out a specific device from the
    active-sessions list. The revoked ``family_id`` is added to the
    family denylist for one access-TTL window, so the in-flight
    access JWT on that device (and any tabs that refreshed off the
    same family) is rejected on the next request — no 20-minute
    grace window.

    If the targeted session belongs to the caller's own refresh
    cookie, the cookie pair is also cleared on this response so the
    SPA reflects the logout immediately.

    Args:
        request: Source of the access cookie (auth) and the refresh
            cookie used to detect self-revocation.
        response: Used to clear auth cookies on self-revocation.
        interactor: Injected revoke-session command handler.
        refresh_store: Used to resolve the caller's refresh cookie to
            its family id for the self-revocation check.
        auth: Injected authenticator that validates the access cookie.
        cfg: Injected security config driving cookie flags.
        session_id: Session (refresh-token family) to revoke. Must
            belong to the caller; cross-user or unknown ids return
            HTTP 404 `EntityNotFound` without leaking which case
            applies.

    Returns:
        `204 No Content` on success. When the caller revoked their
        own session, `Set-Cookie` headers also clear `accessCookie`
        and `refreshCookie`.

    Raises:
        InvalidTokenError: No valid access cookie; HTTP 401.
        EntityNotFoundError: Session does not exist for the caller;
            HTTP 404.
    """
    ctx = await auth.authenticate(request)

    is_current = False
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        record = await refresh_store.resolve(raw_refresh)
        if (
            record is not None
            and record.user_id == ctx.user_id
            and record.family_id == session_id
        ):
            is_current = True

    await interactor.run(
        RevokeSessionCommand(
            user_id=ctx.user_id,
            family_id=session_id,
        ),
    )
    if is_current:
        clear_auth_cookies(response, cfg)
