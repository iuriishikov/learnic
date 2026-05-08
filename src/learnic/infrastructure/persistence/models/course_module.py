import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.course_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.course_module.models import CourseModule
from learnic.entities.course_module.value_objects import (
    ModuleDescription,
    ModuleTitle,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry

course_modules_table = sa.Table(
    "course_modules",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "title",
        sa.String(MODULE_TITLE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "description",
        sa.String(MODULE_DESCRIPTION_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "position",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.Index(
        "ix_course_modules_product_position",
        "product_id",
        "position",
    ),
)


_module_mapped = False


def map_course_module_table() -> None:
    """Apply imperative mapping from :class:`CourseModule`."""
    global _module_mapped  # noqa: PLW0603
    if _module_mapped:
        return
    mapper_registry.map_imperatively(
        CourseModule,
        course_modules_table,
        properties={
            "oid": course_modules_table.c.oid,
            "product_id": course_modules_table.c.product_id,
            "title": composite(
                ModuleTitle,
                course_modules_table.c.title,
            ),
            "description": composite(
                ModuleDescription.of_optional,
                course_modules_table.c.description,
            ),
            "position": course_modules_table.c.position,
            "created_at": course_modules_table.c.created_at,
            "updated_at": course_modules_table.c.updated_at,
        },
        column_prefix="_col_",
    )
    _module_mapped = True
