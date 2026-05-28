from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.teacher_ranking import (
    TeacherRankingReader,
    TopTeacherView,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import ProductStatus
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.enrollment import (
    enrollments_table,
)
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.user import users_table


class TeacherRankingReaderAlchemy(TeacherRankingReader):
    """Computes the user ranking with a single aggregate query.

    The shape is: ``users`` LEFT JOIN ``products`` (only ``PUBLISHED``
    rows count toward the metrics, but the outer join keeps users with
    no published product in the result) LEFT JOIN ``enrollments`` (only
    ``ACTIVE`` rows, so revoked access does not inflate the count).
    ``COUNT(DISTINCT enrollments.student_id)`` collapses a student
    enrolled in several of a teacher's courses to one, while
    ``COUNT(DISTINCT products.oid)`` counts the published catalog; both
    fold to ``0`` for a user who has taught nothing. The avatar is
    folded in via an outer join on the live (non-soft-deleted) ``files``
    row so the caller renders a thumbnail without an N+1.

    Every registered, non-banned user appears; those with no students
    sort to the tail. Cheap enough to compute on demand at MVP scale; if
    the platform grows this can move behind a materialised view without
    changing the :class:`TeacherRankingReader` contract.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def top_by_students(
        self,
        pagination: Pagination,
    ) -> list[TopTeacherView]:
        avatar = files_table.alias("avatar")

        student_count = sa.func.count(
            sa.distinct(enrollments_table.c.student_id),
        ).label("student_count")
        published_product_count = sa.func.count(
            sa.distinct(products_table.c.oid),
        ).label("published_product_count")

        stmt = (
            sa.select(
                users_table.c.oid,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                avatar.c.size_bytes.label("avatar_size_bytes"),
                student_count,
                published_product_count,
            )
            .select_from(
                users_table.outerjoin(
                    products_table,
                    sa.and_(
                        products_table.c.author_id == users_table.c.oid,
                        products_table.c.status
                        == ProductStatus.PUBLISHED.value,
                    ),
                )
                .outerjoin(
                    enrollments_table,
                    sa.and_(
                        enrollments_table.c.product_id
                        == products_table.c.oid,
                        enrollments_table.c.status
                        == EnrollmentStatus.ACTIVE.value,
                    ),
                )
                .outerjoin(
                    avatar,
                    sa.and_(
                        users_table.c.avatar_file_id == avatar.c.oid,
                        avatar.c.deleted_at.is_(None),
                    ),
                )
            )
            .where(users_table.c.is_banned.is_(False))
            .group_by(
                users_table.c.oid,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                avatar.c.oid,
                avatar.c.storage_name,
                avatar.c.bucket,
                avatar.c.content_type,
                avatar.c.size_bytes,
            )
            .order_by(
                student_count.desc(),
                published_product_count.desc(),
                users_table.c.last_name.asc(),
                users_table.c.first_name.asc(),
                users_table.c.oid.asc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            TopTeacherView(
                oid=UserID(row.oid),
                first_name=row.first_name,
                last_name=row.last_name,
                patronymic=row.patronymic,
                is_verified=row.is_verified,
                avatar=(
                    FileMeta(
                        oid=FileID(row.avatar_oid),
                        storage_name=row.avatar_storage_name,
                        bucket=row.avatar_bucket,
                        content_type=row.avatar_content_type,
                        size_bytes=row.avatar_size_bytes,
                    )
                    if row.avatar_oid is not None
                    else None
                ),
                student_count=row.student_count,
                published_product_count=row.published_product_count,
            )
            for row in rows
        ]
