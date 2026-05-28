"""SQLAlchemy mapping for :class:`Statistic`.

The base ``statistics`` table holds shared columns and the
``type`` discriminator. Each :class:`StatisticType` has its own
``statistic_<type>`` subtype table with a composite
``(statistic_id, type)`` foreign key + CHECK constraint pinning
the subtype to its type — that prevents "profile-view-shaped"
subtype rows from attaching to "product-view-type" parent rows
at the database level.

Mapping is imperative so :class:`Statistic` stays ORM-free. The
polymorphic ``details`` field is intentionally NOT mapped — the
gateway writes the matching subtype row alongside the parent
through the per-type spec registry. Adding a new type therefore
never touches this module beyond appending a new
``statistic_<type>_table`` definition and registering it in the
spec layer; the gateway code is unchanged.
"""

from enum import StrEnum

import sqlalchemy as sa

from learnic.entities.statistic.constants import REFERRER_MAX_LEN
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


statistics_table = sa.Table(
    "statistics",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "actor_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "oid",
        "type",
        name="uq_statistics_oid_type",
    ),
    sa.Index(
        "ix_stat_actor_created",
        "actor_id",
        sa.column("created_at").desc(),
    ),
    sa.Index(
        "ix_stat_type_created",
        "type",
        sa.column("created_at").desc(),
    ),
)


statistic_profile_view_table = sa.Table(
    "statistic_profile_view",
    mapper_registry.metadata,
    sa.Column(
        "statistic_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "target_user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "referrer",
        sa.String(REFERRER_MAX_LEN),
        nullable=True,
    ),
    sa.ForeignKeyConstraint(
        ["statistic_id", "type"],
        ["statistics.oid", "statistics.type"],
        ondelete="CASCADE",
        name="fk_stat_profile_view_parent",
    ),
    sa.CheckConstraint(
        f"type = '{StatisticType.PROFILE_VIEW.value}'",
        name="ck_stat_profile_view_type",
    ),
    sa.Index(
        "ix_stat_profile_view_target",
        "target_user_id",
    ),
)


statistic_product_view_table = sa.Table(
    "statistic_product_view",
    mapper_registry.metadata,
    sa.Column(
        "statistic_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "referrer",
        sa.String(REFERRER_MAX_LEN),
        nullable=True,
    ),
    sa.ForeignKeyConstraint(
        ["statistic_id", "type"],
        ["statistics.oid", "statistics.type"],
        ondelete="CASCADE",
        name="fk_stat_product_view_parent",
    ),
    sa.CheckConstraint(
        f"type = '{StatisticType.PRODUCT_VIEW.value}'",
        name="ck_stat_product_view_type",
    ),
    sa.Index(
        "ix_stat_product_view_product",
        "product_id",
    ),
)


statistic_registration_table = sa.Table(
    "statistic_registration",
    mapper_registry.metadata,
    sa.Column(
        "statistic_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["statistic_id", "type"],
        ["statistics.oid", "statistics.type"],
        ondelete="CASCADE",
        name="fk_stat_registration_parent",
    ),
    sa.CheckConstraint(
        f"type = '{StatisticType.REGISTRATION.value}'",
        name="ck_stat_registration_type",
    ),
)


statistic_enrollment_table = sa.Table(
    "statistic_enrollment",
    mapper_registry.metadata,
    sa.Column(
        "statistic_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["statistic_id", "type"],
        ["statistics.oid", "statistics.type"],
        ondelete="CASCADE",
        name="fk_stat_enrollment_parent",
    ),
    sa.CheckConstraint(
        f"type = '{StatisticType.ENROLLMENT.value}'",
        name="ck_stat_enrollment_type",
    ),
    sa.Index(
        "ix_stat_enrollment_product",
        "product_id",
    ),
)


statistic_site_visit_table = sa.Table(
    "statistic_site_visit",
    mapper_registry.metadata,
    sa.Column(
        "statistic_id",
        sa.Uuid,
        primary_key=True,
    ),
    sa.Column(
        "type",
        sa.Enum(
            StatisticType,
            name="statistic_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.ForeignKeyConstraint(
        ["statistic_id", "type"],
        ["statistics.oid", "statistics.type"],
        ondelete="CASCADE",
        name="fk_stat_site_visit_parent",
    ),
    sa.CheckConstraint(
        f"type = '{StatisticType.SITE_VISIT.value}'",
        name="ck_stat_site_visit_type",
    ),
)


_mapped = False


def map_statistic_table() -> None:
    """Imperative mapping for :class:`Statistic`.

    ``details`` is loaded by the gateway out-of-band through the
    per-type spec registry. Subtype tables are pure SA Core
    writes / reads; they do not carry their own ORM mapping
    because the domain side already lives on
    :class:`StatisticDetails` subclasses (no shared base entity).
    """
    global _mapped  # noqa: PLW0603
    if _mapped:
        return
    mapper_registry.map_imperatively(
        Statistic,
        statistics_table,
        properties={
            "oid": statistics_table.c.oid,
            "type": statistics_table.c.type,
            "actor_id": statistics_table.c.actor_id,
            "created_at": statistics_table.c.created_at,
        },
        column_prefix="_col_",
    )
    _mapped = True
