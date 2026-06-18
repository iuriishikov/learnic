from typing import Protocol


class SecurityPolicies(Protocol):
    """Auth-related runtime parameters consumed by application handlers.

    Implementations live in ``infrastructure/`` (``SecurityConfig``
    already satisfies the contract structurally). Handlers depend on
    this Protocol — not on the concrete pydantic-settings class — so
    the application layer stays free of infrastructure imports
    (CLAUDE.md core rule 1).
    """

    frontend_base_url: str
    access_token_ttl_seconds: int
    signup_session_ttl_seconds: int
    reset_password_token_ttl_seconds: int
