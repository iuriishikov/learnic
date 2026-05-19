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


class NotResourceOwnerError(ApplicationError):
    """Raised when a user attempts an operation on a resource they don't own.

    Carries ``resource_id`` and ``user_id`` for logging; clients see
    only ``{"error": "NotResourceOwner"}`` (HTTP 403).
    """

    def __init__(self, resource_id: object, user_id: object) -> None:
        super().__init__(
            f"User {user_id!r} is not allowed to operate on resource {resource_id!r}",
        )
        self.resource_id = resource_id
        self.user_id = user_id


class ProductNotInDraftError(ApplicationError):
    """Raised when an operation requires a product to be in draft status.

    Currently raised on delete attempts against published / archived
    products — drafts can be deleted freely; everything else must be
    archived first to preserve enrollments and history.
    """

    def __init__(self, product_id: object, status: str) -> None:
        super().__init__(
            f"Product {product_id!r} is not in draft (status={status!r})",
        )
        self.product_id = product_id
        self.status = status


class ProductNotArchivedError(ApplicationError):
    """Raised when an unarchive is attempted on a non-archived product.

    Currently raised by the unarchive endpoint when the product is
    in any status other than ``ARCHIVED`` — there is nothing to
    restore. Surfaces as HTTP 409.
    """

    def __init__(self, product_id: object, status: str) -> None:
        super().__init__(
            f"Product {product_id!r} is not archived (status={status!r})",
        )
        self.product_id = product_id
        self.status = status


class ProductNameAlreadyTakenError(ApplicationError):
    """Raised when product name uniqueness is violated for an author.

    Names are unique per author, case-sensitive, including
    archived products. Different authors may use the same name.
    Carries ``name`` for logging; clients see
    ``{"error": "ProductNameAlreadyTaken"}`` (HTTP 409).
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"Product name {name!r} is already taken")
        self.name = name


class EnrollmentClosedError(ApplicationError):
    """Raised when enrolling into a cohort whose status isn't ``OPEN``."""

    def __init__(self, cohort_id: object, status: str) -> None:
        super().__init__(
            f"Cohort {cohort_id!r} enrollment is {status!r} (must be 'open')",
        )
        self.cohort_id = cohort_id
        self.status = status


class AlreadyEnrolledError(ApplicationError):
    """Raised when a duplicate enrollment is attempted.

    Carries ``parent_id`` (cohort or product) and ``student_id`` for
    logging. Clients see ``{"error": "AlreadyEnrolled"}``.
    """

    def __init__(self, parent_id: object, student_id: object) -> None:
        super().__init__(
            f"Student {student_id!r} is already enrolled into {parent_id!r}",
        )
        self.parent_id = parent_id
        self.student_id = student_id


class WrongBlockTypeError(ApplicationError):
    """Raised when an update is sent to a block of a different type.

    E.g. ``PATCH .../blocks/{id}/html`` was issued for a block
    whose actual type is ``katex``. Surfaces as HTTP 409.
    """

    def __init__(self, block_id: object, expected: str, actual: str) -> None:
        super().__init__(
            f"Block {block_id!r} is of type {actual!r}, expected {expected!r}",
        )
        self.block_id = block_id
        self.expected = expected
        self.actual = actual


class WrongFileContentTypeError(ApplicationError):
    """Raised when a file's stored ``content_type`` doesn't match the slot.

    A file-backed block enforces a content-type prefix at construction
    time (``video/`` for video-file blocks, ``image/`` for collage
    items). The check happens server-side against ``files.content_type``
    — the client cannot lie its way past it by mislabelling the upload.
    Surfaces as HTTP 415 Unsupported Media Type.
    """

    def __init__(
        self,
        file_id: object,
        expected_prefix: str,
        actual: str,
    ) -> None:
        super().__init__(
            f"File {file_id!r} has content_type {actual!r}, "
            f"expected to start with {expected_prefix!r}",
        )
        self.file_id = file_id
        self.expected_prefix = expected_prefix
        self.actual = actual


class StorageQuotaExceededError(ApplicationError):
    """Raised when a user's storage usage would exceed the plan limit.

    Carries the plan code, current usage in bytes, the size of the
    attempted upload, and the plan's storage cap so the SPA can render
    a precise message ("0.4 GB attempted on a 2 GB FREE plan, 1.7 GB
    already used"). Surfaces as HTTP 413 Payload Too Large.
    """

    def __init__(
        self,
        plan_code: str,
        used_bytes: int,
        attempted_bytes: int,
        limit_bytes: int,
    ) -> None:
        super().__init__(
            f"Plan {plan_code!r} cap is {limit_bytes} bytes; "
            f"{used_bytes} already used and {attempted_bytes} attempted",
        )
        self.plan_code = plan_code
        self.used_bytes = used_bytes
        self.attempted_bytes = attempted_bytes
        self.limit_bytes = limit_bytes


class CrossCourseLessonMoveError(ApplicationError):
    """Raised when a lesson is moved to a module of a different course.

    Lessons carry a denormalised ``product_id``; cross-course moves
    would invalidate it. Surfaces as HTTP 409.
    """

    def __init__(
        self,
        lesson_id: object,
        source_product_id: object,
        target_product_id: object,
    ) -> None:
        super().__init__(
            f"Lesson {lesson_id!r} cannot move from "
            f"product {source_product_id!r} to {target_product_id!r}",
        )
        self.lesson_id = lesson_id
        self.source_product_id = source_product_id
        self.target_product_id = target_product_id


class InvalidReorderError(ApplicationError):
    """Raised when a full-reorder request doesn't match server state.

    The supplied ``ordered_ids`` must equal the set of existing
    children (no missing, no extra, no duplicates). Surfaces as
    HTTP 409 — clients should reload and retry with fresh ids.
    """


class CannotPublishCourseDirectlyError(ApplicationError):
    """Raised when ``POST /products/{id}/publish`` is called for a course.

    Courses are published implicitly by creating their first
    release; the standalone publish endpoint exists only for
    webinar products.
    """

    def __init__(self, product_id: object) -> None:
        super().__init__(
            f"Course {product_id!r} must be published via release",
        )
        self.product_id = product_id


class CannotEnrollInUnreleasedCourseError(ApplicationError):
    """Raised when a student tries to enroll into a course with no releases."""

    def __init__(self, product_id: object) -> None:
        super().__init__(
            f"Course {product_id!r} has no releases yet — cannot enroll",
        )
        self.product_id = product_id


class CohortFullError(ApplicationError):
    """Raised when a cohort's participant cap is reached."""

    def __init__(self, cohort_id: object) -> None:
        super().__init__(f"Cohort {cohort_id!r} is full")
        self.cohort_id = cohort_id


class InsufficientPermissionsError(ApplicationError):
    """Raised when a collaborator lacks the requested permission.

    Carries ``permission`` (the permission that was demanded),
    ``product_id`` (always set), ``user_id``, and the optional
    ``target_id`` for resource-scoped checks. Surfaces as HTTP 403.
    """

    def __init__(
        self,
        *,
        user_id: object,
        product_id: object,
        permission: str,
        target_id: object = None,
    ) -> None:
        super().__init__(
            f"User {user_id!r} lacks permission {permission!r} "
            f"on product {product_id!r}",
        )
        self.user_id = user_id
        self.product_id = product_id
        self.permission = permission
        self.target_id = target_id


class CannotInviteOwnerError(ApplicationError):
    """Raised when an invite is sent to the product's author.

    The author is short-circuited to all permissions in
    :class:`Authorizer`, so a redundant collaboration row is
    forbidden. Surfaces as HTTP 409.
    """

    def __init__(self, product_id: object, user_id: object) -> None:
        super().__init__(
            f"User {user_id!r} owns product {product_id!r} — cannot invite",
        )
        self.product_id = product_id
        self.user_id = user_id


class CollaborationAlreadyExistsError(ApplicationError):
    """Raised when an active or pending invite already exists.

    Surfaces as HTTP 409. Carries ``product_id`` plus either
    ``collaborator_id`` or ``invited_email`` depending on which
    invite path triggered the conflict.
    """

    def __init__(
        self,
        *,
        product_id: object,
        collaborator_id: object = None,
        invited_email: object = None,
    ) -> None:
        super().__init__(
            f"Collaboration already exists for product {product_id!r}",
        )
        self.product_id = product_id
        self.collaborator_id = collaborator_id
        self.invited_email = invited_email


class RoleInUseError(ApplicationError):
    """Raised when a custom role is deleted while still assigned.

    Carries the ``role_id``; the API client must reassign the
    affected collaborators (or revoke them) before retrying.
    Surfaces as HTTP 409.
    """

    def __init__(self, role_id: object) -> None:
        super().__init__(f"Role {role_id!r} is still in use")
        self.role_id = role_id


class RoleNameAlreadyTakenError(ApplicationError):
    """Raised on per-product role-name uniqueness violation."""

    def __init__(self, product_id: object, name: str) -> None:
        super().__init__(
            f"Role name {name!r} is already taken in product {product_id!r}",
        )
        self.product_id = product_id
        self.name = name


class InviteEmailMismatchError(ApplicationError):
    """Raised when an accept attempt comes from a different email.

    The accepting user's email must match the email the invite was
    issued to. Surfaces as HTTP 403.
    """


class EmailInviteRateLimitExceededError(ApplicationError):
    """Raised when an actor exceeds the per-day email-invite cap.

    Email invitations consume tokens with the upstream email
    provider; the limit shields the quota from a single account
    spamming invites to attacker-controlled addresses. Carries
    ``actor_id``, the configured ``limit``, and ``retry_after_seconds``
    so the HTTP layer can populate the standard ``Retry-After``
    header. Surfaces as HTTP 429.
    """

    def __init__(
        self,
        *,
        actor_id: object,
        limit: int,
        retry_after_seconds: int,
    ) -> None:
        super().__init__(
            f"User {actor_id!r} exceeded the email-invite limit of {limit} per day",
        )
        self.actor_id = actor_id
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds
