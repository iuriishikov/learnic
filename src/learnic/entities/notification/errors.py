from learnic.entities.common.errors import DomainError


class AlreadyReadError(DomainError):
    """Raised when ``mark_read()`` is called on a notification that is already read.

    Idempotency belongs in the command handler — the entity is
    strict to make double-marks visible at the domain level. The
    application command layer translates this into a no-op for
    the HTTP boundary.
    """
