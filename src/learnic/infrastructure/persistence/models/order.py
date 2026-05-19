from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.models import Order
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.value_objects import MinorAmount, Money
from learnic.infrastructure.persistence.models.registry import mapper_registry
from learnic.infrastructure.persistence.models.wallet import currency_enum


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def _money_factory(amount_value: int, currency: Currency) -> Money:
    """Reconstruct :class:`Money` from raw column values on load.

    The columns store ``int`` + ``currency`` enum; the VO needs a
    :class:`MinorAmount` wrapper plus the enum value. The factory is
    NOT marked ``of_optional`` because :attr:`Order.price` is never
    ``None`` — orders without prices are not orders.
    """
    return Money(MinorAmount(amount_value), currency)


orders_table = sa.Table(
    "orders",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "student_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("price_amount", sa.BigInteger(), nullable=False),
    sa.Column("price_currency", currency_enum, nullable=False),
    sa.Column("commission_amount", sa.BigInteger(), nullable=False),
    sa.Column(
        "author_freeze_id",
        sa.Uuid,
        sa.ForeignKey("freeze_entries.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "platform_freeze_id",
        sa.Uuid,
        sa.ForeignKey("freeze_entries.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "status",
        sa.Enum(
            OrderStatus,
            name="order_status",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "price_amount >= 0",
        name="ck_orders_price_non_negative",
    ),
    sa.CheckConstraint(
        "commission_amount >= 0",
        name="ck_orders_commission_non_negative",
    ),
    sa.CheckConstraint(
        "commission_amount <= price_amount",
        name="ck_orders_commission_le_price",
    ),
    sa.Index("ix_orders_student_created_desc", "student_id", sa.desc("created_at")),
)


_order_mapped = False


def map_order_table() -> None:
    """Apply imperative mapping from :class:`Order` to ``orders_table``."""
    global _order_mapped  # noqa: PLW0603
    if _order_mapped:
        return
    mapper_registry.map_imperatively(
        Order,
        orders_table,
        properties={
            "oid": orders_table.c.oid,
            "student_id": orders_table.c.student_id,
            "product_id": orders_table.c.product_id,
            "price": composite(
                _money_factory,
                orders_table.c.price_amount,
                orders_table.c.price_currency,
            ),
            "commission_amount": composite(
                MinorAmount,
                orders_table.c.commission_amount,
            ),
            "author_freeze_id": orders_table.c.author_freeze_id,
            "platform_freeze_id": orders_table.c.platform_freeze_id,
            "status": orders_table.c.status,
            "created_at": orders_table.c.created_at,
            "refunded_at": orders_table.c.refunded_at,
        },
        column_prefix="_col_",
    )
    _order_mapped = True
