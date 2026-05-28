from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import composite

from learnic.entities.product.constants import (
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
    ProductVisibility,
)
from learnic.entities.product.models import Product
from learnic.entities.product.qa import ProductQA
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
    QAAnswer,
    QAQuestion,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Return ``.value``s of a ``StrEnum`` for ``sa.Enum.values_callable``.

    By default SQLAlchemy persists ``Enum.name`` (e.g. ``DRAFT``).
    We use ``StrEnum`` whose ``.value`` is the lowercase form
    (``draft``) — store that instead so Python and SQL agree.
    """
    return [member.value for member in enum_cls]


products_table = sa.Table(
    "products",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "author_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "type",
        sa.Enum(
            ProductType,
            name="product_type",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "status",
        sa.Enum(
            ProductStatus,
            name="product_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
    ),
    sa.Column(
        "visibility",
        sa.Enum(
            ProductVisibility,
            name="product_visibility",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=ProductVisibility.PUBLIC.value,
    ),
    sa.Column("name", sa.String(TITLE_MAX_LEN), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("total_duration_in_hours", sa.Integer(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
    sa.Column(
        "cover_file_id",
        sa.Uuid,
        sa.ForeignKey(
            "files.oid",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_products_cover_file_id",
        ),
        nullable=True,
    ),
    # DB-managed search columns — populated by the
    # ``refresh_product_search()`` trigger function (see migration
    # ``ad03search0001``). Never written from app code; not mapped
    # on the ``Product`` entity (see ``exclude_properties`` in
    # ``map_product_table``).
    sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    sa.Column("search_text", sa.Text(), nullable=True),
    sa.Index("ix_products_author_id", "author_id"),
    sa.Index("ix_products_type_status", "type", "status"),
    sa.UniqueConstraint(
        "author_id",
        "name",
        name="uq_products_author_id_name",
    ),
)


product_qa_table = sa.Table(
    "product_qa",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "question",
        sa.String(QA_QUESTION_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "answer",
        sa.String(QA_ANSWER_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "position",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Index(
        "ix_product_qa_product_id_position",
        "product_id",
        "position",
    ),
)


_product_mapped = False
_qa_mapped = False


def map_product_table() -> None:
    """Apply imperative mapping from :class:`Product` to ``products_table``."""
    global _product_mapped  # noqa: PLW0603
    if _product_mapped:
        return
    mapper_registry.map_imperatively(
        Product,
        products_table,
        properties={
            "oid": products_table.c.oid,
            "author_id": products_table.c.author_id,
            "type": products_table.c.type,
            "status": products_table.c.status,
            "visibility": products_table.c.visibility,
            "name": composite(ProductTitle, products_table.c.name),
            "description": composite(
                ProductDescription.of_optional,
                products_table.c.description,
            ),
            "total_duration_in_hours": composite(
                DurationHours.of_optional,
                products_table.c.total_duration_in_hours,
            ),
            "published_at": products_table.c.published_at,
            "created_at": products_table.c.created_at,
            "updated_at": products_table.c.updated_at,
            "cover_file_id": products_table.c.cover_file_id,
        },
        # DB-managed columns — populated by triggers, never read from
        # the domain entity. Excluded so every ``select(Product)``
        # doesn't lug a tsvector + concatenated lower-cased text
        # blob across the wire.
        exclude_properties=["search_vector", "search_text"],
        column_prefix="_col_",
    )
    _product_mapped = True


def map_product_qa_table() -> None:
    """Apply imperative mapping from :class:`ProductQA`."""
    global _qa_mapped  # noqa: PLW0603
    if _qa_mapped:
        return
    mapper_registry.map_imperatively(
        ProductQA,
        product_qa_table,
        properties={
            "oid": product_qa_table.c.oid,
            "product_id": product_qa_table.c.product_id,
            "question": composite(
                QAQuestion,
                product_qa_table.c.question,
            ),
            "answer": composite(QAAnswer, product_qa_table.c.answer),
            "position": product_qa_table.c.position,
        },
        column_prefix="_col_",
    )
    _qa_mapped = True
