"""System role catalog seeded by Alembic.

Each system role has a stable UUID so the seed migration is
idempotent (upsert by ``oid``) and so the application can refer to a
specific system role by name without an extra DB lookup. Adding a new
system role means appending to :data:`SYSTEM_ROLES` and writing a new
Alembic migration that inserts that single row — never re-seed
existing rows in place because production may already carry custom
permission overrides applied by an administrator.
"""

import uuid
from dataclasses import dataclass
from typing import Final

from learnic.entities.role.constants import (
    COMMENTOR_POSITION,
    EDITOR_POSITION,
    MODERATOR_POSITION,
    VIEWER_POSITION,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission


@dataclass(slots=True, frozen=True)
class SystemRoleSeed:
    oid: RoleID
    name: str
    description: str
    permissions: frozenset[Permission]
    position: int


VIEWER_ROLE_ID: Final = RoleID(
    uuid.UUID("00000000-0000-0000-0000-000000000001"),
)
COMMENTOR_ROLE_ID: Final = RoleID(
    uuid.UUID("00000000-0000-0000-0000-000000000002"),
)
EDITOR_ROLE_ID: Final = RoleID(
    uuid.UUID("00000000-0000-0000-0000-000000000003"),
)
MODERATOR_ROLE_ID: Final = RoleID(
    uuid.UUID("00000000-0000-0000-0000-000000000004"),
)


SYSTEM_ROLES: Final[tuple[SystemRoleSeed, ...]] = (
    SystemRoleSeed(
        oid=VIEWER_ROLE_ID,
        name="Viewer",
        description="Read-only access to the product.",
        permissions=frozenset({Permission.READ_PRODUCT}),
        position=VIEWER_POSITION,
    ),
    SystemRoleSeed(
        oid=COMMENTOR_ROLE_ID,
        name="Commentor",
        description="Read access plus the ability to leave comments.",
        permissions=frozenset(
            {Permission.READ_PRODUCT, Permission.COMMENT},
        ),
        position=COMMENTOR_POSITION,
    ),
    SystemRoleSeed(
        oid=EDITOR_ROLE_ID,
        name="Editor",
        description=(
            "Edit product content (description, cover, modules, lessons, "
            "and Q&A). Cannot publish, archive, or manage collaborators."
        ),
        permissions=frozenset(
            {
                Permission.READ_PRODUCT,
                Permission.COMMENT,
                Permission.EDIT_DESCRIPTION,
                Permission.EDIT_COVER,
                Permission.EDIT_MODULES,
                Permission.EDIT_LESSONS,
                Permission.EDIT_QA,
            },
        ),
        position=EDITOR_POSITION,
    ),
    SystemRoleSeed(
        oid=MODERATOR_ROLE_ID,
        name="Moderator",
        description=(
            "Editor permissions plus release management, publish/archive, "
            "and collaborator management."
        ),
        permissions=frozenset(
            {
                Permission.READ_PRODUCT,
                Permission.COMMENT,
                Permission.EDIT_DESCRIPTION,
                Permission.EDIT_COVER,
                Permission.EDIT_MODULES,
                Permission.EDIT_LESSONS,
                Permission.EDIT_QA,
                Permission.MANAGE_RELEASES,
                Permission.MANAGE_COLLABORATORS,
                Permission.PUBLISH,
                Permission.ARCHIVE,
            },
        ),
        position=MODERATOR_POSITION,
    ),
)


SYSTEM_ROLE_IDS: Final[frozenset[RoleID]] = frozenset(role.oid for role in SYSTEM_ROLES)
