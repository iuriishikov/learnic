from fastapi import Response

from learnic.application.commands.auth.common import TokenPair
from learnic.infrastructure.configs import SecurityConfig

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
SIGNUP_SESSION_COOKIE = "signup_session"

REFRESH_COOKIE_PATH = "/auth/refresh"
SIGNUP_SESSION_COOKIE_PATH = "/auth"


def set_auth_cookies(response: Response, pair: TokenPair, cfg: SecurityConfig) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=pair.access_token,
        max_age=cfg.access_token_ttl_seconds,
        path="/",
        domain=cfg.cookie_domain,
        secure=cfg.cookie_secure,
        httponly=True,
        samesite=cfg.cookie_samesite,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=pair.refresh_token,
        max_age=cfg.refresh_token_ttl_seconds,
        path=REFRESH_COOKIE_PATH,
        domain=cfg.cookie_domain,
        secure=cfg.cookie_secure,
        httponly=True,
        samesite=cfg.cookie_samesite,
    )


def clear_auth_cookies(response: Response, cfg: SecurityConfig) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE,
        path="/",
        domain=cfg.cookie_domain,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        domain=cfg.cookie_domain,
    )


def set_signup_session_cookie(
    response: Response, raw_token: str, cfg: SecurityConfig
) -> None:
    response.set_cookie(
        key=SIGNUP_SESSION_COOKIE,
        value=raw_token,
        max_age=cfg.signup_session_ttl_seconds,
        path=SIGNUP_SESSION_COOKIE_PATH,
        domain=cfg.cookie_domain,
        secure=cfg.cookie_secure,
        httponly=True,
        samesite=cfg.cookie_samesite,
    )


def clear_signup_session_cookie(response: Response, cfg: SecurityConfig) -> None:
    response.delete_cookie(
        key=SIGNUP_SESSION_COOKIE,
        path=SIGNUP_SESSION_COOKIE_PATH,
        domain=cfg.cookie_domain,
    )
