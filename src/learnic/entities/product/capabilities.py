from enum import StrEnum
from typing import Final

from learnic.entities.product.enums import ProductType


class ProductCapability(StrEnum):
    """Operation a product type may or may not support.

    Each :class:`ProductType` declares its set of capabilities in
    :data:`PRODUCT_TYPE_CAPABILITIES`. Handlers gate type-specific
    operations through :meth:`Product.require_supports` instead of
    spreading ``if product.type is not ProductType.COURSE`` checks
    across the codebase.

    Adding a new :class:`ProductType` requires adding a row to
    :data:`PRODUCT_TYPE_CAPABILITIES`; the module-load ``assert``
    below fails-fast on omission.
    """

    HAS_COURSE_CONTENT = "has_course_content"
    """Owns a draftable course tree (modules / lessons / blocks)."""

    HAS_COURSE_RELEASES = "has_course_releases"
    """Publishes versioned snapshots of its course content."""

    HAS_COURSE_ENROLLMENT = "has_course_enrollment"
    """Accepts asynchronous student enrollments into the course."""


PRODUCT_TYPE_CAPABILITIES: Final[dict[ProductType, frozenset[ProductCapability]]] = {
    ProductType.COURSE: frozenset(
        {
            ProductCapability.HAS_COURSE_CONTENT,
            ProductCapability.HAS_COURSE_RELEASES,
            ProductCapability.HAS_COURSE_ENROLLMENT,
        },
    ),
}


# Fail-fast: any ProductType without a capabilities row crashes the
# process at import time, not in a later authorization check.
_missing_types = set(ProductType) - set(PRODUCT_TYPE_CAPABILITIES)
if _missing_types:
    raise RuntimeError(
        "PRODUCT_TYPE_CAPABILITIES is incomplete; missing entries for: "
        f"{sorted(t.value for t in _missing_types)}",
    )
