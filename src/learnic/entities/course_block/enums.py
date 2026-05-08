from enum import StrEnum


class BlockType(StrEnum):
    """Discriminator for lesson-block types.

    Each value matches a child table name (``html_blocks`` →
    ``BlockType.HTML``) and the discriminator field on the public
    Pydantic union schema. Provider-specific embeds (Rutube,
    later YouTube/Vimeo if needed) get their own type values
    rather than a unified ``video`` type — the embed contract is
    always provider-specific in practice (id format, embed URL
    template, optional metadata), so a single ``video`` type
    would be a fake abstraction over diverging concretes.
    """

    HTML = "html"
    KATEX = "katex"
    RUTUBE_VIDEO = "rutube_video"
