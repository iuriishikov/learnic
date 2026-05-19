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
    CODE = "code"
    # Interactive answer blocks. The question prompt itself lives in a
    # preceding HTML block — these block types carry ONLY the answer
    # field and the (server-side, never leaked) correctness data.
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TEXT_INPUT = "text_input"
    # File-backed blocks. The actual bytes live in S3 via the ``files``
    # table; the block carries the FK plus an optional author-facing
    # title. ``VIDEO_FILE`` is the uploaded-video counterpart to
    # ``RUTUBE_VIDEO`` (provider-hosted) — both kept as separate types
    # since their playback contracts diverge.
    FILE = "file"
    VIDEO_FILE = "video_file"
    PHOTO_COLLAGE = "photo_collage"


class CodeBlockLanguage(StrEnum):
    """Supported syntax-highlight languages for :class:`CodeBlock`.

    The set is bounded by the frontend tokenizer
    (``shared/ui/code-block-tokenize.ts``) — every value here must
    be renderable client-side. Adding a language means landing the
    tokenizer support first, then extending this enum (and the
    persisted `String(16)` column tolerates new members without a
    DB migration).
    """

    # JS / TS family
    TSX = "tsx"
    TS = "ts"
    JSX = "jsx"
    JS = "js"
    # Backend
    PYTHON = "python"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    PHP = "php"
    RUBY = "ruby"
    # Systems
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    # Web markup / styles
    HTML = "html"
    XML = "xml"
    CSS = "css"
    SCSS = "scss"
    # Data / config
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    SQL = "sql"
    GRAPHQL = "graphql"
    # Markup
    MARKDOWN = "markdown"
    # Shell
    BASH = "bash"
    SH = "sh"
    DOCKERFILE = "dockerfile"
    # Fallback
    PLAIN = "plain"
