from enum import StrEnum


class BlogPostBlockType(StrEnum):
    """Discriminator for blog-post block types.

    Each value matches a child table name (``blog_post_html_blocks``
    → ``BlogPostBlockType.HTML``) and the discriminator field on the
    public Pydantic union schema. ``IMAGE`` and ``VIDEO`` are both
    file-backed (bytes live in S3 via the ``files`` table); ``HTML``
    carries sanitized inline markup. Adding a variant means a new
    child table, a new entity class, a new view, and a new
    ``add_*``/``update_*`` gateway method — keep the set small.
    """

    IMAGE = "image"
    HTML = "html"
    VIDEO = "video"
