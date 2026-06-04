"""Per-parent count caps as a small reusable domain primitive.

A ``ResourceLimit`` pairs a magnitude (``max_count``) with the
resource it guards and the check itself (``ensure``). The count of
existing rows is supplied by the caller — an application handler that
fetched it via a Gateway/Reader — so the domain stays free of
persistence. Exceeding the cap raises ``ResourceLimitReachedError``,
which the HTTP boundary maps to ``409 Conflict``: the request is valid,
but the current state forbids it until something is deleted (not a
retry/`429` situation).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from learnic.entities.common.errors import DomainError


class LimitedResource(StrEnum):
    """Closed set of resources that carry a per-parent count cap.

    The value is the stable string the API returns in the 409 body so
    the SPA can branch on a known set rather than parse free-form text.
    """

    LESSON_BLOCK = "lesson_block"
    PRODUCT = "product"
    USER_EXPERIENCE = "user_experience"
    NOTE_MODULE = "note_module"
    NOTE_LESSON = "note_lesson"
    NOTE_RELEASE = "note_release"
    PRODUCT_QA = "product_qa"
    ROLE = "role"
    PRODUCT_COLLABORATION = "product_collaboration"
    PUSH_SUBSCRIPTION = "push_subscription"
    BLOG_POST_BLOCK = "blog_post_block"


class ResourceLimitReachedError(DomainError):
    """Creating one more would exceed the per-parent cap.

    Carries the offending ``resource`` and its ``limit`` so the HTTP
    layer can return a precise body. The ``DomainError`` metaclass
    turns this annotated class into a frozen-ish dataclass error.
    """

    resource: LimitedResource
    limit: int


@dataclass(frozen=True, slots=True)
class ResourceLimit:
    """A named per-parent count cap with its own enforcement."""

    resource: LimitedResource
    max_count: int

    def ensure(self, current: int) -> None:
        """Raise if ``current`` already meets or exceeds the cap.

        Args:
            current: Number of existing rows under the parent.

        Raises:
            ResourceLimitReachedError: When ``current >= max_count``.
        """
        if current >= self.max_count:
            raise ResourceLimitReachedError(
                resource=self.resource,
                limit=self.max_count,
            )


# Single auditable registry of per-parent count caps. These are abuse
# guards (not value-object invariants), so they live here rather than in
# each aggregate's ``constants.py``. Starting values — tune freely.
LESSON_BLOCK_LIMIT: Final = ResourceLimit(LimitedResource.LESSON_BLOCK, 200)
PRODUCT_LIMIT: Final = ResourceLimit(LimitedResource.PRODUCT, 200)
USER_EXPERIENCE_LIMIT: Final = ResourceLimit(LimitedResource.USER_EXPERIENCE, 50)
NOTE_MODULE_LIMIT: Final = ResourceLimit(LimitedResource.NOTE_MODULE, 200)
NOTE_LESSON_LIMIT: Final = ResourceLimit(LimitedResource.NOTE_LESSON, 200)
NOTE_RELEASE_LIMIT: Final = ResourceLimit(
    LimitedResource.NOTE_RELEASE, 100,
)
PRODUCT_QA_LIMIT: Final = ResourceLimit(LimitedResource.PRODUCT_QA, 100)
ROLE_LIMIT: Final = ResourceLimit(LimitedResource.ROLE, 100)
PRODUCT_COLLABORATION_LIMIT: Final = ResourceLimit(
    LimitedResource.PRODUCT_COLLABORATION, 200,
)
PUSH_SUBSCRIPTION_LIMIT: Final = ResourceLimit(
    LimitedResource.PUSH_SUBSCRIPTION, 20,
)
BLOG_POST_BLOCK_LIMIT: Final = ResourceLimit(
    LimitedResource.BLOG_POST_BLOCK, 200,
)
