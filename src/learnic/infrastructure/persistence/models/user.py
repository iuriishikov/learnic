import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import composite

from learnic.entities.user.constants import (
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PASSWORD_HASH_MAX_LEN,
    PATRONYMIC_MAX_LEN,
    PORTFOLIO_URL_MAX_LEN,
    PUBLIC_EMAIL_MAX_LEN,
    WEBSITE_URL_MAX_LEN,
)
from learnic.entities.user.models import User
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
    Patronymic,
    PortfolioUrl,
    PublicEmail,
    UserDescription,
    WebsiteUrl,
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
    sa.Column(
        "password_hash",
        sa.String(PASSWORD_HASH_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "email_verified",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column(
        "is_verified",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column(
        "is_admin",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column(
        "is_banned",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column(
        "description",
        sa.Text(),
        nullable=True,
    ),
    sa.Column(
        "avatar_file_id",
        sa.Uuid,
        sa.ForeignKey(
            "files.oid",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_users_avatar_file_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "cover_file_id",
        sa.Uuid,
        sa.ForeignKey(
            "files.oid",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_users_cover_file_id",
        ),
        nullable=True,
    ),
    sa.Column(
        "website_url",
        sa.String(WEBSITE_URL_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "portfolio_url",
        sa.String(PORTFOLIO_URL_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "public_email",
        sa.String(PUBLIC_EMAIL_MAX_LEN),
        nullable=True,
    ),
    # Timestamp of the user's consent to distribution of their personal
    # data (ст. 10.1 152-ФЗ). NULL = no consent on record. Set at
    # registration when the optional checkbox is ticked.
    sa.Column(
        "distribution_consent_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ),
    # Full-text + fuzzy search over the user's name fields. Both columns
    # are DB-managed (rebuilt by the ``refresh_user_search`` trigger, see
    # migration ``usrsearch0001``) and excluded from the entity mapping.
    sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    sa.Column("search_text", sa.Text(), nullable=True),
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
            "password_hash": composite(
                PasswordHash,
                users_table.c.password_hash,
            ),
            "email_verified": users_table.c.email_verified,
            "is_verified": users_table.c.is_verified,
            "is_admin": users_table.c.is_admin,
            "is_banned": users_table.c.is_banned,
            "description": composite(
                UserDescription.of_optional,
                users_table.c.description,
            ),
            "avatar_file_id": users_table.c.avatar_file_id,
            "cover_file_id": users_table.c.cover_file_id,
            "website_url": composite(
                WebsiteUrl.of_optional,
                users_table.c.website_url,
            ),
            "portfolio_url": composite(
                PortfolioUrl.of_optional,
                users_table.c.portfolio_url,
            ),
            "public_email": composite(
                PublicEmail.of_optional,
                users_table.c.public_email,
            ),
            "distribution_consent_at": users_table.c.distribution_consent_at,
        },
        # DB-managed search columns are not part of the domain entity.
        exclude_properties=["search_vector", "search_text"],
        column_prefix="_col_",
    )
    _mapped = True
