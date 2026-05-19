"""drop purchase + webinar tables, reshape enrollments

Post-pivot cleanup: the platform no longer ships paid purchases
(wallets / orders / freeze + ledger entries) or webinar products
(cohorts / schedules / sessions). The corresponding tables and
PG enums are dropped, and the unified ``enrollments`` table is
collapsed back to a course-only shape:

* ``type`` enum (``course``, ``webinar``) becomes ``kind``
  (``course`` only).
* ``status`` enum loses ``completed`` and ``refunded``, gains
  ``revoked``. Completion is now signalled by
  ``enrollment_course_details.completed_at`` while the parent row
  stays ``active``; refunds are dead concept and map to
  ``revoked`` (semantic match — both remove access).
* ``UNIQUE(product_id, student_id)`` moves from the course
  side-detail to the parent ``enrollments`` row so the constraint
  lives on a single table; ``product_id`` is hoisted up to
  ``enrollments`` and removed from
  ``enrollment_course_details``. ``student_id`` was denormalised
  on the side-detail too — drop the duplicate there.

This migration is destructive — none of the payment / webinar
state can be reconstructed from the remaining schema. The
downgrade is a sketch: enums and column shapes come back, but
the dropped tables do not. Full restore requires checking out
the ``archive/purchases-webinars-enrollment`` branch.

Revision ID: z1pivot0001
Revises: p0k1l2m3n4o5
Create Date: 2026-05-19 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "z1pivot0001"
down_revision: Union[str, Sequence[str], None] = "p0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ---- A. Drop payment tables (children → parents) --------------- #
    op.drop_index(
        "ix_orders_student_created_desc", table_name="orders",
    )
    op.drop_table("orders")

    op.drop_index(
        "ix_ledger_entries_wallet_created_desc",
        table_name="ledger_entries",
    )
    op.drop_table("ledger_entries")

    op.drop_index(
        "ix_freeze_entries_wallet_status",
        table_name="freeze_entries",
    )
    op.drop_index("ix_freeze_entries_ripe", table_name="freeze_entries")
    op.drop_table("freeze_entries")

    op.drop_index("uq_wallets_platform_currency", table_name="wallets")
    op.drop_index("uq_wallets_user_currency", table_name="wallets")
    op.drop_table("wallets")

    # ---- B. Drop webinar tables (children → parents) --------------- #
    op.drop_table("enrollment_webinar_details")

    op.drop_index(
        "ix_webinar_sessions_cohort_id_starts_at",
        table_name="webinar_sessions",
    )
    op.drop_table("webinar_sessions")

    op.drop_index(
        "ix_webinar_schedules_cohort_id",
        table_name="webinar_schedules",
    )
    op.drop_table("webinar_schedules")

    op.drop_index("ix_cohorts_host_id", table_name="cohorts")
    op.drop_index("ix_cohorts_webinar_id", table_name="cohorts")
    op.drop_table("cohorts")

    op.drop_table("product_webinar_details")

    # ---- C. Reshape enrollments ------------------------------------ #
    # C1. Hoist product_id up from enrollment_course_details to
    #     enrollments (nullable first → backfill → NOT NULL).
    op.add_column(
        "enrollments",
        sa.Column("product_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        UPDATE enrollments
        SET product_id = ecd.product_id
        FROM enrollment_course_details AS ecd
        WHERE ecd.enrollment_id = enrollments.oid
        """,
    )
    op.alter_column("enrollments", "product_id", nullable=False)
    op.create_foreign_key(
        "fk_enrollments_product_id",
        "enrollments", "products",
        ["product_id"], ["oid"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_enrollments_product_student",
        "enrollments",
        ["product_id", "student_id"],
    )

    # C2. Drop denormalised columns + their FKs / UNIQUE on the
    #     course side-detail. Constraint names for the unnamed FKs
    #     are the Postgres auto-generated defaults
    #     (``<table>_<column>_fkey``); the unique constraint is the
    #     explicit name from ``aa1b8cde7f01_unify_enrollments``.
    op.drop_constraint(
        "uq_enrollment_course_details_product_student",
        "enrollment_course_details",
        type_="unique",
    )
    op.drop_constraint(
        "enrollment_course_details_product_id_fkey",
        "enrollment_course_details",
        type_="foreignkey",
    )
    op.drop_column("enrollment_course_details", "product_id")
    op.drop_constraint(
        "enrollment_course_details_student_id_fkey",
        "enrollment_course_details",
        type_="foreignkey",
    )
    op.drop_column("enrollment_course_details", "student_id")

    # C3. Rename enrollments.type → kind, migrate enrollment_type
    #     enum (``course``, ``webinar``) → enrollment_kind
    #     (``course`` only). The webinar value has no live rows
    #     (the enrollment_webinar_details table was just dropped;
    #     any orphan ``webinar`` enrollment rows would have failed
    #     the side-detail join anyway — migrate them defensively
    #     by deleting first).
    op.execute("DELETE FROM enrollments WHERE type::text = 'webinar'")
    op.execute("CREATE TYPE enrollment_kind AS ENUM ('course')")
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN type TYPE enrollment_kind "
        "USING type::text::enrollment_kind",
    )
    op.alter_column("enrollments", "type", new_column_name="kind")
    op.execute("DROP TYPE enrollment_type")

    # C4. Replace enrollment_status enum:
    #     before: (active, completed, refunded)
    #     after:  (active, revoked)
    #     mapping: completed → active   (course-completion now
    #                                     lives on completed_at)
    #              refunded  → revoked  (both remove access)
    op.execute(
        "ALTER TABLE enrollments ALTER COLUMN status DROP DEFAULT",
    )
    op.execute(
        "ALTER TYPE enrollment_status RENAME TO enrollment_status_old",
    )
    op.execute(
        "CREATE TYPE enrollment_status AS ENUM ('active', 'revoked')",
    )
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN status TYPE enrollment_status "
        "USING (CASE status::text "
        "  WHEN 'completed' THEN 'active' "
        "  WHEN 'refunded' THEN 'revoked' "
        "  ELSE status::text END)::enrollment_status",
    )
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN status SET DEFAULT 'active'",
    )
    op.execute("DROP TYPE enrollment_status_old")

    # The composite (kind, status) index from
    # ``aa1b8cde7f01`` was named ``ix_enrollments_type_status``; the
    # SA model wants it as ``ix_enrollments_kind_status``. Rename to
    # match — Postgres ``ALTER INDEX ... RENAME TO`` is cheap.
    op.execute(
        "ALTER INDEX ix_enrollments_type_status "
        "RENAME TO ix_enrollments_kind_status",
    )

    # ---- D. Shrink product_type enum: drop the ``webinar`` value -- #
    # No live rows reference ``webinar`` (the
    # ``product_webinar_details`` table was just dropped; the FK
    # there used ``ON DELETE CASCADE`` against ``products.oid``,
    # but ``products`` itself kept the row — so any leftover
    # ``products.type = 'webinar'`` rows would now be orphaned
    # detail-less rows. Delete them defensively before the cast.
    op.execute("DELETE FROM products WHERE type::text = 'webinar'")
    op.execute("ALTER TYPE product_type RENAME TO product_type_old")
    op.execute("CREATE TYPE product_type AS ENUM ('course')")
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN type TYPE product_type "
        "USING type::text::product_type",
    )
    op.execute("DROP TYPE product_type_old")

    # ---- E. Drop the per-product price column. -------------------- #
    # ``price_amount`` (BigInteger, nullable) and its non-negative
    # check constraint came back in ``aa01b2c3d4e5_add_wallet_order_tables``
    # after the original ``a1c4d7f928b3_drop_product_price`` cull;
    # with the payment surface gone again the column has no live
    # consumer. Drop the constraint before the column so Postgres
    # does not refuse the column drop.
    op.drop_constraint(
        "ck_products_price_non_negative",
        "products",
        type_="check",
    )
    op.drop_column("products", "price_amount")

    # ---- F. Drop now-orphaned PG enums ----------------------------- #
    # All of these were defined by the dropped payment / webinar
    # tables and no live column references them anymore. Use
    # IF EXISTS so re-running on a partially-applied DB does not
    # explode.
    for enum_name in (
        # payment side
        "order_status",
        "ledger_kind",
        "freeze_status",
        "freeze_source",
        "wallet_owner_kind",
        "currency",
        # webinar side
        "webinar_session_status",
        "cohort_lifecycle_status",
        "cohort_enrollment_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")


def downgrade() -> None:
    """Downgrade schema (sketch only).

    Destructive migration: the dropped payment / webinar tables
    are not recreated here — full restore requires checking out
    the ``archive/purchases-webinars-enrollment`` branch and
    re-applying its forward migrations. What we do restore is
    the *shape* of the enrollments / products surface (column
    names, enum value sets, denormalised columns) so a hard
    rollback doesn't leave the schema in a half-state.
    """
    # ---- Restore the per-product price column. -------------------- #
    # Added back nullable with the non-negative check constraint, no
    # backfill — the upstream payment surface that populated it is
    # gone (see the upgrade docstring).
    op.add_column(
        "products",
        sa.Column("price_amount", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_products_price_non_negative",
        "products",
        "price_amount IS NULL OR price_amount >= 0",
    )

    # ---- Restore product_type with the ``webinar`` value ----------- #
    op.execute("ALTER TYPE product_type RENAME TO product_type_old")
    op.execute("CREATE TYPE product_type AS ENUM ('course', 'webinar')")
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN type TYPE product_type "
        "USING type::text::product_type",
    )
    op.execute("DROP TYPE product_type_old")

    # ---- Restore enrollment_status with the old value set --------- #
    op.execute(
        "ALTER TABLE enrollments ALTER COLUMN status DROP DEFAULT",
    )
    op.execute(
        "ALTER TYPE enrollment_status RENAME TO enrollment_status_old",
    )
    op.execute(
        "CREATE TYPE enrollment_status AS ENUM "
        "('active', 'completed', 'refunded')",
    )
    # ``revoked`` had no slot in the old enum — map it back to
    # ``refunded`` (closest semantic match, since both removed
    # access in the pre-pivot world).
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN status TYPE enrollment_status "
        "USING (CASE status::text "
        "  WHEN 'revoked' THEN 'refunded' "
        "  ELSE status::text END)::enrollment_status",
    )
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN status SET DEFAULT 'active'",
    )
    op.execute("DROP TYPE enrollment_status_old")

    # ---- Rename kind → type + restore enrollment_type enum -------- #
    op.execute(
        "ALTER INDEX ix_enrollments_kind_status "
        "RENAME TO ix_enrollments_type_status",
    )
    op.alter_column("enrollments", "kind", new_column_name="type")
    op.execute("CREATE TYPE enrollment_type AS ENUM ('course', 'webinar')")
    op.execute(
        "ALTER TABLE enrollments "
        "ALTER COLUMN type TYPE enrollment_type "
        "USING type::text::enrollment_type",
    )
    op.execute("DROP TYPE enrollment_kind")

    # ---- Drop the new constraints + product_id on enrollments ----- #
    op.drop_constraint(
        "uq_enrollments_product_student",
        "enrollments",
        type_="unique",
    )
    op.drop_constraint(
        "fk_enrollments_product_id",
        "enrollments",
        type_="foreignkey",
    )

    # ---- Re-add denormalised columns on enrollment_course_details - #
    # Nullable, no backfill — the upgrade dropped these and there
    # is no source to refill them from once the payment / webinar
    # state is gone.
    op.add_column(
        "enrollment_course_details",
        sa.Column("student_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "enrollment_course_details_student_id_fkey",
        "enrollment_course_details", "users",
        ["student_id"], ["oid"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "enrollment_course_details",
        sa.Column("product_id", sa.Uuid(), nullable=True),
    )
    # Backfill product_id on the side-detail from the parent
    # before we drop the parent's column.
    op.execute(
        """
        UPDATE enrollment_course_details AS ecd
        SET product_id = e.product_id
        FROM enrollments AS e
        WHERE e.oid = ecd.enrollment_id
        """,
    )
    op.create_foreign_key(
        "enrollment_course_details_product_id_fkey",
        "enrollment_course_details", "products",
        ["product_id"], ["oid"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_enrollment_course_details_product_student",
        "enrollment_course_details",
        ["product_id", "student_id"],
    )

    op.drop_column("enrollments", "product_id")

    # ---- Recreate enums dropped by the upgrade (empty types) ------ #
    # The original tables that used these are not recreated here
    # (see docstring); the enums come back so a downstream
    # migration that re-creates the tables can rely on them
    # existing without duplicating the CREATE TYPE statements.
    op.execute("CREATE TYPE currency AS ENUM ('RUB')")
    op.execute(
        "CREATE TYPE wallet_owner_kind AS ENUM ('user', 'platform')",
    )
    op.execute(
        "CREATE TYPE freeze_source AS ENUM "
        "('sale_hold', 'commission_hold')",
    )
    op.execute(
        "CREATE TYPE freeze_status AS ENUM "
        "('frozen', 'released', 'cancelled')",
    )
    op.execute(
        "CREATE TYPE ledger_kind AS ENUM ("
        "'purchase', 'freeze', 'release', 'refund', "
        "'cancel_freeze', 'topup', 'adjustment')",
    )
    op.execute("CREATE TYPE order_status AS ENUM ('paid', 'refunded')")
    op.execute(
        "CREATE TYPE cohort_enrollment_status AS ENUM "
        "('open', 'closed', 'full')",
    )
    op.execute(
        "CREATE TYPE cohort_lifecycle_status AS ENUM "
        "('upcoming', 'active', 'completed', 'cancelled')",
    )
    op.execute(
        "CREATE TYPE webinar_session_status AS ENUM "
        "('scheduled', 'rescheduled', 'cancelled', 'completed')",
    )
