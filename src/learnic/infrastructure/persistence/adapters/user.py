from datetime import datetime
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
    UserSummaryView,
    UserView,
)
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
)
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import normalize_email
from learnic.infrastructure.persistence.models.email_token import (
    email_tokens_table,
)
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.signup_session import (
    signup_sessions_table,
)
from learnic.infrastructure.persistence.models.user import users_table


class UserMapperAlchemy(UserGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: UserID) -> User | None:
        stmt = sa.select(User).where(users_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def with_email(self, email: str) -> User | None:
        # Normalize the same way the Email VO does so a casing/whitespace
        # variant still resolves to the stored account.
        stmt = sa.select(User).where(
            users_table.c.email == normalize_email(email)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _abandoned_unverified_where(
        self,
        now: datetime,
    ) -> tuple[sa.ColumnElement[bool], ...]:
        # "Abandoned" = unverified AND unable to self-recover: no live
        # VERIFY token (email link dead) and no live signup session
        # (resend impossible). Login is then blocked and the UNIQUE
        # email blocks re-registration, so the row squats the address
        # forever — safe and necessary to delete. email_tokens /
        # signup_sessions children cascade via ON DELETE CASCADE; an
        # abandoned signup never logged in, so nothing else refs it.
        # Shared verbatim by the bulk purge and the per-email reclaim
        # so the two can never drift on what "abandoned" means.
        active_verify_token = (
            sa.select(sa.literal(1))
            .select_from(email_tokens_table)
            .where(
                email_tokens_table.c.user_id == users_table.c.oid,
                email_tokens_table.c.purpose
                == EmailTokenPurpose.VERIFY.value,
                email_tokens_table.c.consumed_at.is_(None),
                email_tokens_table.c.expires_at > now,
            )
            .correlate(users_table)
            .exists()
        )
        active_signup_session = (
            sa.select(sa.literal(1))
            .select_from(signup_sessions_table)
            .where(
                signup_sessions_table.c.user_id == users_table.c.oid,
                signup_sessions_table.c.expires_at > now,
            )
            .correlate(users_table)
            .exists()
        )
        return (
            users_table.c.email_verified.is_(False),
            ~active_verify_token,
            ~active_signup_session,
        )

    @override
    async def delete_abandoned_unverified(self, now: datetime) -> int:
        stmt = sa.delete(users_table).where(
            *self._abandoned_unverified_where(now),
        )
        result = await self._session.execute(stmt)
        rowcount: int | None = getattr(result, "rowcount", None)
        return rowcount or 0

    @override
    async def delete_abandoned_unverified_by_email(
        self,
        email: str,
        now: datetime,
    ) -> bool:
        # Same liveness gate as the bulk purge, scoped to one address
        # so a fresh registration can reclaim it on demand. Normalize
        # the email the same way the Email VO / ``with_email`` do so a
        # casing/whitespace variant still targets the stored row.
        stmt = sa.delete(users_table).where(
            users_table.c.email == normalize_email(email),
            *self._abandoned_unverified_where(now),
        )
        result = await self._session.execute(stmt)
        rowcount: int | None = getattr(result, "rowcount", None)
        return (rowcount or 0) > 0


class UserReaderAlchemy(UserReader):
    """Read-side projections for user profiles.

    Ban-visibility policy (deliberate, applied consistently): a banned
    user is removed from *discovery* surfaces — ``search_by_name`` and
    the admins / top-teachers lists filter ``is_banned = False`` — but a
    direct ``with_id`` profile read stays resolvable. That keeps content
    the banned user authored (notes, blog posts) from breaking its
    author link, and the returned ``UserView`` carries the ``is_banned``
    flag so the SPA can badge or collapse the profile as it sees fit. If
    the product later wants a hard "banned users have no public profile"
    rule, add ``is_banned.is_(False)`` here and to the experience /
    social-link readers in one change — do not split the policy.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: UserID) -> UserView | None:
        avatar = files_table.alias("avatar")
        cover = files_table.alias("cover")

        stmt = (
            sa.select(
                users_table.c.oid,
                users_table.c.email,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                users_table.c.description,
                users_table.c.website_url,
                users_table.c.portfolio_url,
                users_table.c.public_email,
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                avatar.c.size_bytes.label("avatar_size_bytes"),
                cover.c.oid.label("cover_oid"),
                cover.c.storage_name.label("cover_storage_name"),
                cover.c.bucket.label("cover_bucket"),
                cover.c.content_type.label("cover_content_type"),
                cover.c.size_bytes.label("cover_size_bytes"),
            )
            .select_from(
                users_table.outerjoin(
                    avatar,
                    sa.and_(
                        users_table.c.avatar_file_id == avatar.c.oid,
                        avatar.c.deleted_at.is_(None),
                    ),
                ).outerjoin(
                    cover,
                    sa.and_(
                        users_table.c.cover_file_id == cover.c.oid,
                        cover.c.deleted_at.is_(None),
                    ),
                )
            )
            .where(users_table.c.oid == oid)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None

        return UserView(
            oid=UserID(row.oid),
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            patronymic=row.patronymic,
            is_verified=row.is_verified,
            description=row.description,
            website_url=row.website_url,
            portfolio_url=row.portfolio_url,
            public_email=row.public_email,
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
            cover=(
                FileMeta(
                    oid=FileID(row.cover_oid),
                    storage_name=row.cover_storage_name,
                    bucket=row.cover_bucket,
                    content_type=row.cover_content_type,
                    size_bytes=row.cover_size_bytes,
                )
                if row.cover_oid is not None
                else None
            ),
        )

    @override
    async def is_admin(self, oid: UserID) -> bool | None:
        stmt = sa.select(users_table.c.is_admin).where(
            users_table.c.oid == oid,
        )
        return await self._session.scalar(stmt)

    @override
    async def admins(
        self,
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        avatar = files_table.alias("avatar")

        stmt = (
            sa.select(
                users_table.c.oid,
                users_table.c.email,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                users_table.c.is_banned,
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                avatar.c.size_bytes.label("avatar_size_bytes"),
            )
            .select_from(
                users_table.outerjoin(
                    avatar,
                    sa.and_(
                        users_table.c.avatar_file_id == avatar.c.oid,
                        avatar.c.deleted_at.is_(None),
                    ),
                )
            )
            .where(
                users_table.c.is_admin.is_(True),
                users_table.c.is_banned.is_(False),
            )
            .order_by(
                users_table.c.last_name.asc(),
                users_table.c.first_name.asc(),
                users_table.c.oid.asc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            UserSummaryView(
                oid=UserID(row.oid),
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                patronymic=row.patronymic,
                is_verified=row.is_verified,
                is_banned=row.is_banned,
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
            )
            for row in rows
        ]

    @override
    async def search_by_name(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        # Full-text + trigram fuzzy over the name fields, mirroring the
        # product catalog search. ``search_text`` is stored lower-cased
        # by the trigger, so the query is lowered too (trigram ops are
        # case-sensitive; tsvector matching is dictionary-driven and is
        # case-insensitive regardless).
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        # Default ``word_similarity_threshold = 0.6`` is too strict for
        # short name queries — one extra char past a typo collapses the
        # score below the cutoff. 0.4 still rejects noise. ``SET LOCAL``
        # scopes the change to this transaction.
        await self._session.execute(
            sa.text("SET LOCAL pg_trgm.word_similarity_threshold = 0.4"),
        )
        # ``websearch_to_tsquery`` tolerates arbitrary input (quoted
        # phrases, OR, leading ``-``) without raising. The regconfig is
        # cast verbatim so asyncpg's ``$N::VARCHAR`` params don't break
        # overload resolution (same trick as the product search).
        russian_regconfig: sa.ColumnElement[str] = sa.literal_column(
            "'russian'::regconfig",
        )
        tsq = sa.func.websearch_to_tsquery(russian_regconfig, query_lower)
        rank_ts = sa.func.ts_rank_cd(
            users_table.c.search_vector, tsq,
        ).label("rank_ts")
        # ``word_similarity`` scores the best-matching word substring —
        # the right operator for a short query against a short name text.
        rank_trgm = sa.func.word_similarity(
            query_lower, users_table.c.search_text,
        ).label("rank_trgm")

        avatar = files_table.alias("avatar")

        stmt = (
            sa.select(
                users_table.c.oid,
                users_table.c.email,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                users_table.c.is_banned,
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                avatar.c.size_bytes.label("avatar_size_bytes"),
                rank_ts,
                rank_trgm,
            )
            .select_from(
                users_table.outerjoin(
                    avatar,
                    sa.and_(
                        users_table.c.avatar_file_id == avatar.c.oid,
                        avatar.c.deleted_at.is_(None),
                    ),
                )
            )
            .where(
                sa.or_(
                    users_table.c.search_vector.op("@@")(tsq),
                    users_table.c.search_text.op("%>")(query_lower),
                )
            )
            # tsvector (morphology + weights) carries twice the weight of
            # trigram (typos/transliteration); tie-break by name then
            # ``oid`` for stable pagination across equal-rank rows.
            .order_by(
                (rank_ts * sa.literal(2.0) + rank_trgm).desc(),
                users_table.c.last_name.asc(),
                users_table.c.first_name.asc(),
                users_table.c.oid.asc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            UserSummaryView(
                oid=UserID(row.oid),
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                patronymic=row.patronymic,
                is_verified=row.is_verified,
                is_banned=row.is_banned,
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
            )
            for row in rows
        ]
