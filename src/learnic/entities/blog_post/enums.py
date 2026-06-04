from enum import StrEnum


class BlogPostStatus(StrEnum):
    """Lifecycle status of a blog post.

    A post starts as ``DRAFT`` — visible only on the admin surface —
    and becomes ``PUBLISHED`` when an administrator publishes it, at
    which point it appears on the public read endpoints. The set is
    intentionally tiny: there is no separate ``archived`` state today
    (an admin either keeps a post published or unpublishes it back to
    draft); add a variant here AND revisit every status guard on
    :class:`~learnic.entities.blog_post.models.BlogPost` if that
    changes.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
