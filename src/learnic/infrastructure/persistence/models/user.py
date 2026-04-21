import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.user.constants import (
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PATRONYMIC_MAX_LEN,
)
from learnic.entities.user.models import User
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    Patronymic,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry

users_table = sa.Table(
    "users",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "email",
        sa.String(EMAIL_MAX_LEN),
        nullable=False,
        unique=True,
    ),
    sa.Column(
        "first_name",
        sa.String(FIRST_NAME_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "last_name",
        sa.String(LAST_NAME_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "patronymic",
        sa.String(PATRONYMIC_MAX_LEN),
        nullable=True,
    ),
)


_mapped = False


def map_user_table() -> None:
    """Apply imperative mapping from :class:`User` to ``users_table``.

    Idempotent: safe to call multiple times, which matters when
    ``create_app_tests`` is invoked per-test and shares the module-level
    ``mapper_registry``.
    """
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        User,
        users_table,
        properties={
            "oid": users_table.c.oid,
            "email": composite(Email, users_table.c.email),
            "first_name": composite(FirstName, users_table.c.first_name),
            "last_name": composite(LastName, users_table.c.last_name),
            "patronymic": composite(
                Patronymic.of_optional,
                users_table.c.patronymic,
            ),
        },
        column_prefix="_col_",
    )
    _mapped = True
