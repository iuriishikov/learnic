"""merge enrollments and tags heads

Two independent migration branches were live in the repo before
this point:

* ``aa1b8cde7f01`` (``unify_enrollments``) branched off
  ``z0a7bcd5e6f7`` and folds the ``course_enrollments`` +
  ``webinar_enrollments`` tables into a single ``enrollments``
  table.
* ``aabbtags0001`` (``add_tags``) sits on top of
  ``ab01merge0000`` and introduces the global ``tags`` pool +
  ``product_tags`` association table.

Both heads need to be applied for the DB schema to match the
mapped SQLAlchemy models (the unified ``enrollments`` table on
one side, the tag pool + product_tags association on the other).
This revision is the topological merge — no DDL, just a single
parent pointer that unifies the chain so ``alembic upgrade head``
resolves to one revision again.

Revision ID: ac02merge0001
Revises: aa1b8cde7f01, aabbtags0001
Create Date: 2026-05-18 02:26:39.494842

"""

from typing import Sequence, Union

revision: str = "ac02merge0001"
down_revision: Union[str, Sequence[str], None] = (
    "aa1b8cde7f01",
    "aabbtags0001",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
