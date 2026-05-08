"""rename latex blocks to katex blocks

Renames the ``'latex'`` enum value of ``lesson_block_type`` to
``'katex'`` and the two backing tables (``latex_blocks`` →
``katex_blocks`` and ``course_release_latex_blocks`` →
``course_release_katex_blocks``).

Storage shape and content stay identical — KaTeX is a strict
subset of LaTeX, and this codebase's renderer is KaTeX
specifically; using ``'katex'`` everywhere makes the
expected-input surface explicit.

Revision ID: d4a8f7c12e90
Revises: c7e2f5a91d4b
Create Date: 2026-05-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "d4a8f7c12e90"
down_revision: Union[str, Sequence[str], None] = "c7e2f5a91d4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PG 10+ supports ALTER TYPE ... RENAME VALUE in-place — no rewrites
    # of existing rows required.
    op.execute(
        "ALTER TYPE lesson_block_type RENAME VALUE 'latex' TO 'katex'",
    )
    op.rename_table("latex_blocks", "katex_blocks")
    op.rename_table(
        "course_release_latex_blocks",
        "course_release_katex_blocks",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table(
        "course_release_katex_blocks",
        "course_release_latex_blocks",
    )
    op.rename_table("katex_blocks", "latex_blocks")
    op.execute(
        "ALTER TYPE lesson_block_type RENAME VALUE 'katex' TO 'latex'",
    )
