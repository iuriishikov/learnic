from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.user.constants import SOCIAL_LINK_URL_MAX_LEN
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.value_objects import SocialLinkUrl
from learnic.entities.user_social_link.models import UserSocialLink
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Persist a ``StrEnum`` by its ``value`` (lowercase form)."""
    return [member.value for member in enum_cls]


user_social_links_table = sa.Table(
    "user_social_links",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "kind",
        sa.Enum(
            SocialLinkKind,
            name="social_link_kind",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "url",
        sa.String(SOCIAL_LINK_URL_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "position",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Index(
        "ix_user_social_links_user_id_position",
        "user_id",
        "position",
    ),
)


_mapped = False


def map_user_social_link_table() -> None:
    """Apply imperative mapping from :class:`UserSocialLink`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        UserSocialLink,
        user_social_links_table,
        properties={
            "oid": user_social_links_table.c.oid,
            "user_id": user_social_links_table.c.user_id,
            "kind": user_social_links_table.c.kind,
            "url": composite(
                SocialLinkUrl,
                user_social_links_table.c.url,
            ),
            "position": user_social_links_table.c.position,
        },
        column_prefix="_col_",
    )
    _mapped = True
