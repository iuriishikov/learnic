from enum import StrEnum


class ProductType(StrEnum):
    COURSE = "course"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProductVisibility(StrEnum):
    """Whether a product accepts open self-enrollment or is invite-only.

    Orthogonal to :class:`ProductStatus` (the lifecycle): a product
    can be ``PUBLISHED`` yet ``PRIVATE``. Both ``PUBLIC`` and
    ``PRIVATE`` products are equally **discoverable** — they appear in
    the catalog, search and on their detail page. The only difference
    is enrollment: ``PUBLIC`` products accept self-enrollment, while
    ``PRIVATE`` ones refuse it and can only be joined through a
    gift/invite (see ``product_gifts``).
    """

    PUBLIC = "public"
    PRIVATE = "private"
