"""widen note hard-delete cascade

Admin note hard-delete (``DELETE /admin/notes/{id}``) removes a note by
deleting its ``products`` row and relying on the ``ON DELETE CASCADE``
chain to sweep every child. Two foreign keys *inside* that subtree were
``ON DELETE RESTRICT``, so deleting a note that had enrollments pinned to
a release, or collaborators on a custom role, aborted the whole cascade
with a ``ForeignKeyViolationError`` (surfacing as an unmapped HTTP 500):

* ``enrollment_note_details.release_id`` -> ``note_releases``
* ``collaboration_grants.role_id``       -> ``roles``

Both are flipped to ``ON DELETE CASCADE``. This weakens no application
invariant:

* A release is only ever deleted as part of a full-note delete, where the
  pinning enrollment (and thus its note-details row) is deleted too.
* Custom-role deletion stays gated application-side by ``RoleInUseError``
  *before* any ``DELETE`` is issued. The FK was a redundant DB guard that
  was also *stricter* than the app: it wrongly blocked deleting a role
  that held only dead (declined / revoked) grants. CASCADE aligns the FK
  with the app's "dead grants don't count as in use" semantics.

Revision ID: notedel0001
Revises: fngraph0001
Create Date: 2026-06-12 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "notedel0001"
down_revision: Union[str, Sequence[str], None] = "fngraph0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENR_TABLE = "enrollment_note_details"
_ENR_FK = "fk_enrollment_note_details_release_id"
_GRANT_TABLE = "collaboration_grants"
_GRANT_FK = "collaboration_grants_role_id_fkey"


def upgrade() -> None:
    """Flip the two in-subtree RESTRICT FKs to CASCADE."""
    op.drop_constraint(_ENR_FK, _ENR_TABLE, type_="foreignkey")
    op.create_foreign_key(
        _ENR_FK,
        _ENR_TABLE,
        "note_releases",
        ["release_id"],
        ["oid"],
        ondelete="CASCADE",
    )
    op.drop_constraint(_GRANT_FK, _GRANT_TABLE, type_="foreignkey")
    op.create_foreign_key(
        _GRANT_FK,
        _GRANT_TABLE,
        "roles",
        ["role_id"],
        ["oid"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Restore the original RESTRICT semantics."""
    op.drop_constraint(_GRANT_FK, _GRANT_TABLE, type_="foreignkey")
    op.create_foreign_key(
        _GRANT_FK,
        _GRANT_TABLE,
        "roles",
        ["role_id"],
        ["oid"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(_ENR_FK, _ENR_TABLE, type_="foreignkey")
    op.create_foreign_key(
        _ENR_FK,
        _ENR_TABLE,
        "note_releases",
        ["release_id"],
        ["oid"],
        ondelete="RESTRICT",
    )
