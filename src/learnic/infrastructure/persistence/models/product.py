from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.product.constants import (
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    STREAM_URL_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.models import Product
from learnic.entities.product.qa import ProductQA
from learnic.entities.product.value_objects import (
    AccessWindow,
    DurationHours,
    ParticipantsLimit,
    ProductDescription,
    ProductTitle,
    QAAnswer,
    QAQuestion,
    StreamUrl,
    WebinarLessonsCount,
    WebinarSessionDuration,
)
from learnic.entities.product.webinar_details import WebinarDetails
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
    sa.Index("ix_products_author_id", "author_id"),
    sa.Index("ix_products_type_status", "type", "status"),
    sa.UniqueConstraint(
        "author_id",
        "name",
        name="uq_products_author_id_name",
    ),
)


product_webinar_details_table = sa.Table(
    "product_webinar_details",
    mapper_registry.metadata,
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("total_lessons", sa.Integer(), nullable=False),
    sa.Column("default_duration_minutes", sa.Integer(), nullable=False),
    sa.Column(
        "allow_recording",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column("default_max_participants", sa.Integer(), nullable=True),
    sa.Column(
        "default_stream_url",
        sa.String(STREAM_URL_MAX_LEN),
        nullable=True,
    ),
    sa.Column("access_window_minutes", sa.Integer(), nullable=True),
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
_webinar_details_mapped = False
_qa_mapped = False


def map_product_table() -> None:
    """Apply imperative mapping from :class:`Product` to ``products_table``.

    The ``webinar_details`` slot on :class:`Product` is intentionally
    NOT mapped — it is loaded out-of-band by the
    ``ProductGateway`` adapter (composition split, no ORM
    relationship). The class-level default ``= None`` keeps the
    attribute readable on freshly hydrated instances.
    """
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
        column_prefix="_col_",
    )
    _product_mapped = True


def map_webinar_details_table() -> None:
    """Apply imperative mapping from :class:`WebinarDetails`."""
    global _webinar_details_mapped  # noqa: PLW0603
    if _webinar_details_mapped:
        return
    mapper_registry.map_imperatively(
        WebinarDetails,
        product_webinar_details_table,
        properties={
            "oid": product_webinar_details_table.c.product_id,
            "total_lessons": composite(
                WebinarLessonsCount,
                product_webinar_details_table.c.total_lessons,
            ),
            "default_duration_minutes": composite(
                WebinarSessionDuration,
                product_webinar_details_table.c.default_duration_minutes,
            ),
            "allow_recording": (product_webinar_details_table.c.allow_recording),
            "default_max_participants": composite(
                ParticipantsLimit.of_optional,
                product_webinar_details_table.c.default_max_participants,
            ),
            "default_stream_url": composite(
                StreamUrl.of_optional,
                product_webinar_details_table.c.default_stream_url,
            ),
            "access_window_minutes": composite(
                AccessWindow.of_optional,
                product_webinar_details_table.c.access_window_minutes,
            ),
        },
        column_prefix="_col_",
    )
    _webinar_details_mapped = True


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
