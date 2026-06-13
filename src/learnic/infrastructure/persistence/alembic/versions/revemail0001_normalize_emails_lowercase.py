"""normalize existing emails to lowercase

The ``Email`` value object now lowercases (and trims) on construction,
and ``UserGateway.with_email`` normalizes its lookup the same way, so a
casing variant (``Ada@x.com`` vs ``ada@x.com``) resolves to one account
for register / login / password-reset. This migration brings already-
stored rows into the same canonical form so historical mixed-case
accounts can still log in with any casing.

If two pre-existing rows differ only by case they collide on the
``users.email`` unique constraint and this UPDATE fails loudly — resolve
the duplicate accounts by hand, then re-run. The downgrade is a no-op
(the original casing is not recoverable, and lowercase is the intended
canonical form going forward).

Revision ID: revemail0001
Revises: tagsearch0001
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "revemail0001"
down_revision: Union[str, Sequence[str], None] = "tagsearch0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE users "
        "SET email = lower(btrim(email)) "
        "WHERE email <> lower(btrim(email))",
    )


def downgrade() -> None:
    # Lossy: the original casing is gone and lowercase is the canonical
    # form, so there is nothing meaningful to restore.
    pass
