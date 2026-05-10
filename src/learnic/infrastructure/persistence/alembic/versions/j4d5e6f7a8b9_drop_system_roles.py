"""drop system roles, drop kind column

Removes the system role concept from the data model. Roles are now
exclusively per-product (``product_id`` becomes ``NOT NULL``); the
``kind`` column and the ``role_kind`` enum type are dropped along
with it. The frontend creates an initial role set via onboarding,
so role display names are stored in whichever language the user
typed them — the backend no longer ships seed catalogue rows whose
names would otherwise need synchronised translations on the SPA.

Migration of pre-existing data
------------------------------
``collaboration_grants.role_id`` is ``ON DELETE RESTRICT``, so any
grant that points at a system role row blocks the row's deletion.
Before dropping system roles we materialise per-product copies for
each ``(product_id, system_role_id)`` pair that has at least one
grant and reassign those grants. The replacement row carries the
same name + description + permission set as the original system
role; the per-product position is computed as ``MAX(position) + 10``
inside that product so the new row slots at the bottom of the
product's hierarchy and cannot accidentally outrank an existing
collaborator. Per-product unique-name conflicts are resolved by
suffixing ``" (copy)"`` (and further integers if needed) before
the insert.

Schema changes
--------------
- ``roles.product_id`` becomes ``NOT NULL``.
- The ``COALESCE``-based unique index ``uq_roles_name_per_product``
  is replaced with a plain composite unique constraint on
  ``(product_id, name)``.
- The ``kind`` column and the ``role_kind`` enum type are dropped.

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
Create Date: 2026-05-08 22:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "j4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "i3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COMMENTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")


def _unique_name(
    bind: sa.engine.Connection,
    product_id: uuid.UUID,
    base_name: str,
) -> str:
    """Return a name unique inside ``product_id``, suffixing on collision."""
    candidate = base_name
    suffix = 0
    while True:
        existing = bind.execute(
            sa.text(
                "SELECT 1 FROM roles "
                "WHERE product_id = :pid AND name = :name LIMIT 1",
            ),
            {"pid": product_id, "name": candidate},
        ).first()
        if existing is None:
            return candidate
        suffix += 1
        candidate = (
            f"{base_name} (copy)"
            if suffix == 1
            else f"{base_name} (copy {suffix})"
        )


def _materialise_per_product_replacements(
    bind: sa.engine.Connection,
    actor_id: uuid.UUID | None = None,
) -> None:
    """For every product that grants a system role, create a custom copy.

    Walks ``collaboration_grants`` joined to ``product_collaborations``
    to find each ``(product_id, system_role_id)`` pair, then inserts
    one custom role per pair carrying the same name / description /
    permissions as the source system role and reassigns the grants.
    """
    pairs = bind.execute(
        sa.text(
            "SELECT DISTINCT pc.product_id, g.role_id "
            "FROM collaboration_grants AS g "
            "JOIN product_collaborations AS pc "
            "  ON pc.oid = g.collaboration_id "
            "JOIN roles AS r ON r.oid = g.role_id "
            "WHERE r.kind = 'system'",
        ),
    ).fetchall()

    for product_id, system_role_id in pairs:
        source = bind.execute(
            sa.text(
                "SELECT name, description "
                "FROM roles WHERE oid = :oid",
            ),
            {"oid": system_role_id},
        ).first()
        if source is None:
            continue
        permissions = [
            row[0]
            for row in bind.execute(
                sa.text(
                    "SELECT permission FROM role_permissions "
                    "WHERE role_id = :rid",
                ),
                {"rid": system_role_id},
            ).fetchall()
        ]
        next_position = bind.execute(
            sa.text(
                "SELECT COALESCE(MAX(position), 0) + 10 FROM roles "
                "WHERE product_id = :pid",
            ),
            {"pid": product_id},
        ).scalar_one()
        new_oid = uuid.uuid4()
        new_name = _unique_name(bind, product_id, source.name)

        bind.execute(
            sa.text(
                "INSERT INTO roles "
                "(oid, product_id, kind, name, description, "
                " position, created_by, created_at, updated_at) "
                "VALUES "
                "(:oid, :pid, 'custom', :name, :description, "
                " :position, :created_by, NOW(), NOW())",
            ),
            {
                "oid": new_oid,
                "pid": product_id,
                "name": new_name,
                "description": source.description,
                "position": next_position,
                "created_by": actor_id,
            },
        )
        if permissions:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission) "
                    "VALUES (:rid, :permission)",
                ),
                [
                    {"rid": new_oid, "permission": p}
                    for p in permissions
                ],
            )

        # Drop colliding grants on the new role first (the dest pair
        # cannot exist yet in practice — we just inserted the new role —
        # but keeping the dedup mirrors the prior drop-Viewer-Moderator
        # migration and stays robust under partial-rerun scenarios).
        bind.execute(
            sa.text(
                "DELETE FROM collaboration_grants AS g "
                "WHERE g.role_id = :src "
                "AND EXISTS ("
                "  SELECT 1 FROM collaboration_grants AS h "
                "  WHERE h.role_id = :dst "
                "    AND h.collaboration_id = g.collaboration_id "
                "    AND h.scope_type = g.scope_type "
                "    AND COALESCE(h.scope_id, "
                "          '00000000-0000-0000-0000-000000000000'::uuid) "
                "        = COALESCE(g.scope_id, "
                "          '00000000-0000-0000-0000-000000000000'::uuid)"
                ")",
            ),
            {"src": system_role_id, "dst": new_oid},
        )
        bind.execute(
            sa.text(
                "UPDATE collaboration_grants "
                "SET role_id = :dst "
                "WHERE role_id = :src "
                "AND collaboration_id IN ("
                "  SELECT oid FROM product_collaborations "
                "  WHERE product_id = :pid"
                ")",
            ),
            {"src": system_role_id, "dst": new_oid, "pid": product_id},
        )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # 1. Reassign every grant currently pointing at a system role to a
    #    fresh per-product custom role with the same name + permissions.
    _materialise_per_product_replacements(bind)

    # 2. Delete all remaining system roles. ``role_permissions`` cascades.
    bind.execute(sa.text("DELETE FROM roles WHERE kind = 'system'"))

    # 3. Replace the COALESCE-based unique index with a plain composite
    #    one — ``product_id`` is about to become NOT NULL.
    op.drop_index("uq_roles_name_per_product", table_name="roles")
    op.create_index(
        "uq_roles_name_per_product",
        "roles",
        ["product_id", "name"],
        unique=True,
    )

    # 4. Lock product_id down. After step 2 every remaining row carries
    #    a non-null product_id, so the constraint is satisfiable.
    op.alter_column(
        "roles",
        "product_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    # 5. Drop the kind column and its enum type.
    op.drop_column("roles", "kind")
    op.execute("DROP TYPE role_kind")


def downgrade() -> None:
    """Downgrade schema.

    Reverses the schema changes (re-creates the ``role_kind`` enum +
    ``kind`` column, makes ``product_id`` nullable again, restores the
    COALESCE-based unique index) and re-seeds the two system roles
    (Commentor, Editor) with their original UUIDs and permissions so
    code paths that look them up by id still resolve. Custom roles
    that were materialised during the upgrade are left in place —
    deleting them would orphan the grants pointing at them.
    """
    bind = op.get_bind()

    # 1. Recreate the role_kind enum and the kind column.
    op.execute("CREATE TYPE role_kind AS ENUM ('system', 'custom')")
    op.add_column(
        "roles",
        sa.Column(
            "kind",
            sa.Enum("system", "custom", name="role_kind", create_type=False),
            nullable=True,
        ),
    )
    bind.execute(sa.text("UPDATE roles SET kind = 'custom'"))
    op.alter_column(
        "roles",
        "kind",
        existing_type=sa.Enum(
            "system",
            "custom",
            name="role_kind",
            create_type=False,
        ),
        nullable=False,
    )

    # 2. Make product_id nullable again.
    op.alter_column(
        "roles",
        "product_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    # 3. Restore the COALESCE-based unique index.
    op.drop_index("uq_roles_name_per_product", table_name="roles")
    op.execute(
        "CREATE UNIQUE INDEX uq_roles_name_per_product "
        "ON roles ("
        "COALESCE(product_id, '00000000-0000-0000-0000-000000000000'), "
        "name)",
    )

    # 4. Re-seed the system roles. Custom rows materialised on upgrade
    #    keep their grants — there is no way to know which were derived
    #    from which system role.
    bind.execute(
        sa.text(
            "INSERT INTO roles "
            "(oid, product_id, kind, name, description, "
            " position, created_by) "
            "VALUES "
            "(:oid, NULL, 'system', :name, :description, "
            " :position, NULL)",
        ),
        [
            {
                "oid": _COMMENTOR_ID,
                "name": "Commentor",
                "description": (
                    "Read access plus the ability to leave comments."
                ),
                "position": 300,
            },
            {
                "oid": _EDITOR_ID,
                "name": "Editor",
                "description": (
                    "Edit product content (description, cover, "
                    "modules, lessons, and Q&A). Cannot publish, "
                    "archive, or manage collaborators."
                ),
                "position": 200,
            },
        ],
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission) "
            "VALUES (:role_id, :permission)",
        ),
        [
            {"role_id": _COMMENTOR_ID, "permission": "read_product"},
            {"role_id": _COMMENTOR_ID, "permission": "comment"},
            *(
                {"role_id": _EDITOR_ID, "permission": p}
                for p in (
                    "read_product",
                    "comment",
                    "edit_description",
                    "edit_cover",
                    "edit_modules",
                    "edit_lessons",
                    "edit_qa",
                )
            ),
        ],
    )
