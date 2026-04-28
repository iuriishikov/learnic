class ApplicationError(Exception):
    """Base class for errors raised by application-layer handlers."""


class EntityNotFoundError(ApplicationError):
    """Raised when a lookup by id returns no result."""

    def __init__(self, entity_id: object) -> None:
        super().__init__(f"Entity not found: {entity_id!r}")
        self.entity_id = entity_id


class InvalidCredentialsError(ApplicationError):
    """Raised when email/password authentication fails."""


class InvalidTokenError(ApplicationError):
    """Raised when a token is missing, expired, revoked or malformed."""


class EmailAlreadyRegisteredError(ApplicationError):
    """Raised when registration is attempted with an existing email."""


class EmailNotVerifiedError(ApplicationError):
    """Raised when a user attempts to authenticate before verifying email."""


class UserAvatarNotFoundError(ApplicationError):
    """Raised when a user exists but has no avatar attached."""


class UserCoverNotFoundError(ApplicationError):
    """Raised when a user exists but has no cover attached."""
