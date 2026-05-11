import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.user_experience.constants import (
    DESCRIPTION_MAX_LEN,
    SOURCE_URL_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.user_experience.models import UserExperience
from learnic.entities.user_experience.value_objects import (
    ExperienceDescription,
    ExperienceSourceUrl,
    ExperienceTitle,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry

user_experiences_table = sa.Table(
    "user_experiences",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("title", sa.String(TITLE_MAX_LEN), nullable=False),
    sa.Column("description", sa.String(DESCRIPTION_MAX_LEN), nullable=True),
    sa.Column("start_date", sa.Date(), nullable=False),
    sa.Column("end_date", sa.Date(), nullable=True),
    sa.Column(
        "source_url",
        sa.String(SOURCE_URL_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "icon_file_id",
        sa.Uuid,
        sa.ForeignKey(
            "files.oid",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_user_experiences_icon_file_id",
        ),
        nullable=True,
    ),
    sa.Index(
        "ix_user_experiences_user_id_start_date",
        "user_id",
        sa.text("start_date DESC"),
    ),
)


_mapped = False


def map_user_experience_table() -> None:
    """Apply imperative mapping from :class:`UserExperience`."""
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        UserExperience,
        user_experiences_table,
        properties={
            "oid": user_experiences_table.c.oid,
            "user_id": user_experiences_table.c.user_id,
            "title": composite(
                ExperienceTitle,
                user_experiences_table.c.title,
            ),
            "description": composite(
                ExperienceDescription.of_optional,
                user_experiences_table.c.description,
            ),
            "start_date": user_experiences_table.c.start_date,
            "end_date": user_experiences_table.c.end_date,
            "source_url": composite(
                ExperienceSourceUrl.of_optional,
                user_experiences_table.c.source_url,
            ),
            "icon_file_id": user_experiences_table.c.icon_file_id,
        },
        column_prefix="_col_",
    )
    _mapped = True
