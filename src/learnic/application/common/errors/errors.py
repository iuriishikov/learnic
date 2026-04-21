class ApplicationError(Exception):
    """Base class for errors raised by application-layer handlers."""


class EntityNotFoundError(ApplicationError):
    """Raised when a lookup by id returns no result."""

    def __init__(self, entity_id: object) -> None:
        super().__init__(f"Entity not found: {entity_id!r}")
        self.entity_id = entity_id
