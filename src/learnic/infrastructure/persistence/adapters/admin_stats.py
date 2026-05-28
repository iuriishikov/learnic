from datetime import datetime, timedelta, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.admin_stats import (
    AdminStatsReader,
    AdminStatsView,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.enums import ProductStatus
from learnic.entities.statistic.enums import StatisticType
from learnic.infrastructure.persistence.models.enrollment import (
    enrollments_table,
)
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.statistic import (
    statistics_table,
)
from learnic.infrastructure.persistence.models.user import users_table

_DAU_WINDOW = timedelta(days=1)
_MAU_WINDOW = timedelta(days=30)


class AdminStatsReaderAlchemy(AdminStatsReader):
    """Computes dashboard counters with a handful of aggregate queries.

    One round-trip per aggregate root (users, products, enrollments)
    folds its per-status / per-flag breakdown into a single row via
    Postgres ``FILTER`` clauses. A fourth query derives DAU / MAU from
    the ``site_visit`` activity events as the count of distinct actors
    in a rolling 1-day / 30-day window.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def collect(self) -> AdminStatsView:
        users_stmt = sa.select(
            sa.func.count().label("total"),
            sa.func.count().filter(users_table.c.is_banned).label("banned"),
            sa.func.count().filter(users_table.c.is_admin).label("admins"),
        ).select_from(users_table)
        users_row = (await self._session.execute(users_stmt)).one()

        products_stmt = sa.select(
            sa.func.count().label("total"),
            sa.func.count()
            .filter(products_table.c.status == ProductStatus.DRAFT.value)
            .label("draft"),
            sa.func.count()
            .filter(
                products_table.c.status == ProductStatus.PUBLISHED.value,
            )
            .label("published"),
            sa.func.count()
            .filter(
                products_table.c.status == ProductStatus.ARCHIVED.value,
            )
            .label("archived"),
        ).select_from(products_table)
        products_row = (await self._session.execute(products_stmt)).one()

        enrollments_stmt = sa.select(
            sa.func.count().label("total"),
            sa.func.count()
            .filter(
                enrollments_table.c.status == EnrollmentStatus.ACTIVE.value,
            )
            .label("active"),
        ).select_from(enrollments_table)
        enrollments_row = (await self._session.execute(enrollments_stmt)).one()

        now = datetime.now(timezone.utc)
        activity_stmt = sa.select(
            sa.func.count(sa.distinct(statistics_table.c.actor_id))
            .filter(statistics_table.c.created_at >= now - _DAU_WINDOW)
            .label("dau"),
            sa.func.count(sa.distinct(statistics_table.c.actor_id))
            .filter(statistics_table.c.created_at >= now - _MAU_WINDOW)
            .label("mau"),
        ).where(statistics_table.c.type == StatisticType.SITE_VISIT.value)
        activity_row = (await self._session.execute(activity_stmt)).one()

        return AdminStatsView(
            total_users=users_row.total,
            banned_users=users_row.banned,
            admin_users=users_row.admins,
            total_courses=products_row.total,
            draft_courses=products_row.draft,
            published_courses=products_row.published,
            archived_courses=products_row.archived,
            total_enrollments=enrollments_row.total,
            active_enrollments=enrollments_row.active,
            dau=activity_row.dau,
            mau=activity_row.mau,
        )
