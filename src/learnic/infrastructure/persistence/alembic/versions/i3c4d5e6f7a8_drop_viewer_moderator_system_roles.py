"""drop Viewer and Moderator system roles

Trims the system role catalogue down to ``Commentor`` and ``Editor``.
The ``Viewer`` and ``Moderator`` rows (UUIDs ``...0001`` and
``...0004``) are removed along with their ``role_permissions`` rows.

``collaboration_grants.role_id`` is ``ondelete='RESTRICT'``, so any
existing grant pointing at one of the dropped roles is reassigned
in-place before the role row is deleted:

- ``Viewer``    -> ``Commentor`` (effectively a small upgrade —
  gains ``COMMENT`` on top of the original ``READ_PRODUCT``).
- ``Moderator`` -> ``Editor`` (a deliberate downgrade — loses
  ``PUBLISH`` / ``ARCHIVE`` / ``MANAGE_RELEASES`` /
  ``MANAGE_COLLABORATORS``; the closest surviving role).

Duplicate grants (same collaboration + same scope, both old and new
role) are pruned first to avoid violating ``uq_grant_unique_scope``.

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-05-08 20:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "h2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_COMMENTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_MODERATOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
_DROPPED_IDS: tuple[uuid.UUID, ...] = (_VIEWER_ID, _MODERATOR_ID)
_REASSIGNMENTS: tuple[tuple[uuid.UUID, uuid.UUID], ...] = (
    (_VIEWER_ID, _COMMENTOR_ID),
    (_MODERATOR_ID, _EDITOR_ID),
)


def _reassign_grants(
    bind: sa.engine.Connection, src: uuid.UUID, dst: uuid.UUID
) -> None:
    # Drop grants on ``src`` that would collide with an existing
    # grant on ``dst`` for the same (collaboration, scope, scope_id) —
    # otherwise the UPDATE below would violate uq_grant_unique_scope.
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
        {"src": src, "dst": dst},
    )
    bind.execute(
        sa.text(
            "UPDATE collaboration_grants SET role_id = :dst WHERE role_id = :src",
        ),
        {"src": src, "dst": dst},
    )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    for src, dst in _REASSIGNMENTS:
        _reassign_grants(bind, src, dst)

    # role_permissions has ondelete=CASCADE; deleting the role rows
    # also drops their permission rows. Doing the explicit delete
    # first keeps the migration readable and gives a clear failure
    # site if the FK ever changes.
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id = ANY(:ids)",
        ),
        {"ids": list(_DROPPED_IDS)},
    )
    bind.execute(
        sa.text("DELETE FROM roles WHERE oid = ANY(:ids)"),
        {"ids": list(_DROPPED_IDS)},
    )


def downgrade() -> None:
    """Downgrade schema.

    Re-inserts the role rows and their permission sets. Note: the
    upgrade reassignment of ``collaboration_grants`` is **not**
    reversed — those grants stay on ``Commentor`` / ``Editor``.
    Reverting the role catalogue is enough to unblock further
    downgrades; reconstructing prior grant assignments would require
    knowing the original ``role_id`` per grant, which this migration
    does not preserve.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO roles "
            "(oid, product_id, kind, name, description, "
            "created_by, position) "
            "VALUES "
            "(:oid, NULL, 'system', :name, :description, NULL, "
            ":position)",
        ),
        [
            {
                "oid": _VIEWER_ID,
                "name": "Viewer",
                "description": "Read-only access to the product.",
                "position": 400,
            },
            {
                "oid": _MODERATOR_ID,
                "name": "Moderator",
                "description": (
                    "Editor permissions plus release management, "
                    "publish/archive, and collaborator management."
                ),
                "position": 100,
            },
        ],
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission) "
            "VALUES (:role_id, :permission)",
        ),
        [
            {"role_id": _VIEWER_ID, "permission": "read_product"},
            *(
                {"role_id": _MODERATOR_ID, "permission": p}
                for p in (
                    "read_product",
                    "comment",
                    "edit_description",
                    "edit_cover",
                    "edit_modules",
                    "edit_lessons",
                    "edit_qa",
                    "manage_releases",
                    "manage_collaborators",
                    "publish",
                    "archive",
                )
            ),
        ],
    )
