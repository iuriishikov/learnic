from enum import StrEnum


class ProductType(StrEnum):
    COURSE = "course"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    BANNED = "banned"
