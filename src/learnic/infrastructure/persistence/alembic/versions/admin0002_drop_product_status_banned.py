"""drop the 'banned' value from the product_status enum

Course moderation is now a hard delete (admin-only), not a soft
``BANNED`` status, so the value is removed from the ``product_status``
PostgreSQL enum. PostgreSQL has no ``ALTER TYPE ... DROP VALUE``, so the
type is recreated without ``banned`` and the column re-pointed at it.

Any course that somehow still carries ``banned`` is demoted to
``archived`` first so the ``USING`` cast cannot fail (no code path ever
set ``banned``, so in practice this updates zero rows). Only
``products.status`` uses this type, so the old type can be dropped
cleanly once the column is migrated.

Revision ID: admin0002
Revises: admin0001
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "admin0002"
down_revision: Union[str, Sequence[str], None] = "admin0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE products SET status = 'archived' WHERE status = 'banned'",
    )
    op.execute("ALTER TABLE products ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE product_status RENAME TO product_status_old")
    op.execute(
        "CREATE TYPE product_status AS ENUM ('draft', 'published', 'archived')",
    )
    op.execute(
        "ALTER TABLE products ALTER COLUMN status TYPE product_status "
        "USING status::text::product_status",
    )
    op.execute("ALTER TABLE products ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE product_status_old")


def downgrade() -> None:
    op.execute("ALTER TABLE products ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE product_status RENAME TO product_status_old")
    op.execute(
        "CREATE TYPE product_status AS ENUM "
        "('draft', 'published', 'archived', 'banned')",
    )
    op.execute(
        "ALTER TABLE products ALTER COLUMN status TYPE product_status "
        "USING status::text::product_status",
    )
    op.execute("ALTER TABLE products ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE product_status_old")
