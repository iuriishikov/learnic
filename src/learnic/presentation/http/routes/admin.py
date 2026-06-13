from datetime import date
from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from learnic.application.commands.admin.ban_user import (
    BanUserCommand,
    BanUserCommandHandler,
)
from learnic.application.commands.admin.unban_user import (
    UnbanUserCommand,
    UnbanUserCommandHandler,
)
from learnic.application.commands.admin.delete_note import (
    AdminDeleteNoteCommand,
    AdminDeleteNoteCommandHandler,
)
from learnic.application.common.persistence.admin_metrics import AdminMetric
from learnic.application.common.persistence.admin_stats import AdminStatsView
from learnic.application.queries.admin.get_metric_series import (
    METRICS_DEFAULT_DAYS,
    METRICS_MAX_DAYS,
    METRICS_MIN_DAYS,
    AdminMetricSeries,
    GetAdminMetricSeriesQuery,
    GetAdminMetricSeriesQueryHandler,
)
from learnic.application.queries.admin.get_stats import (
    GetAdminStatsQuery,
    GetAdminStatsQueryHandler,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.queries.user.search import (
    SearchUsersQuery,
    SearchUsersQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.admin_deps import AdminAuthenticator
from learnic.presentation.http.common.auth_deps import access_cookie_scheme
from learnic.presentation.http.common.errors.rules import ADMIN_MAP
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import AdminUserSummarySchema

router = ErrorAwareRouter(
    prefix="/admin",
    tags=["Admin"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_USER_ID_PATH: Final = Path(
    description="Target user's UUID.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)
_NOTE_ID_PATH: Final = Path(
    description="Target note product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


# ----------------------------- response schemas ------------------------ #


class AdminStatsSchema(BaseModel):
    """Platform-wide counters for the admin dashboard.

    Returned by ``GET /admin/stats``. Every field is a live
    ``COUNT(*)`` — the snapshot reflects the moment of the request.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total_users": 1280,
                    "banned_users": 7,
                    "admin_users": 3,
                    "total_notes": 412,
                    "draft_notes": 156,
                    "published_notes": 240,
                    "archived_notes": 16,
                    "total_enrollments": 9043,
                    "active_enrollments": 8771,
                    "dau": 312,
                    "mau": 4180,
                },
            ],
        },
    )

    total_users: int = Field(
        description="Total registered users, including banned ones.",
        ge=0,
        examples=[1280],
    )
    banned_users: int = Field(
        description="Users currently banned from the platform.",
        ge=0,
        examples=[7],
    )
    admin_users: int = Field(
        description="Users carrying the platform-admin flag.",
        ge=0,
        examples=[3],
    )
    total_notes: int = Field(
        description="Total note products across every status.",
        ge=0,
        examples=[412],
    )
    draft_notes: int = Field(
        description="Notes in ``draft`` status.",
        ge=0,
        examples=[156],
    )
    published_notes: int = Field(
        description="Notes in ``published`` status.",
        ge=0,
        examples=[240],
    )
    archived_notes: int = Field(
        description="Notes in ``archived`` status.",
        ge=0,
        examples=[16],
    )
    total_enrollments: int = Field(
        description="Total enrollments across every status.",
        ge=0,
        examples=[9043],
    )
    active_enrollments: int = Field(
        description="Enrollments in ``active`` status.",
        ge=0,
        examples=[8771],
    )
    dau: int = Field(
        description=(
            "Daily active users — distinct users with a `site_visit` "
            "event in the last 24 hours."
        ),
        ge=0,
        examples=[312],
    )
    mau: int = Field(
        description=(
            "Monthly active users — distinct users with a `site_visit` "
            "event in the last 30 days."
        ),
        ge=0,
        examples=[4180],
    )

    @classmethod
    def from_view(cls, view: AdminStatsView) -> Self:
        return cls(
            total_users=view.total_users,
            banned_users=view.banned_users,
            admin_users=view.admin_users,
            total_notes=view.total_notes,
            draft_notes=view.draft_notes,
            published_notes=view.published_notes,
            archived_notes=view.archived_notes,
            total_enrollments=view.total_enrollments,
            active_enrollments=view.active_enrollments,
            dau=view.dau,
            mau=view.mau,
        )


# --------------------------------- routes ------------------------------ #


@router.get(
    "/stats",
    summary="Get platform-wide dashboard statistics",
    operation_id="getAdminStats",
    response_model=AdminStatsSchema,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def get_stats(
    request: Request,
    interactor: FromDishka[GetAdminStatsQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
) -> AdminStatsSchema:
    """Return aggregate counters for the admin dashboard.

    Admin-only. Counts users (total / banned / admins), notes
    (total + per lifecycle status), and enrollments (total / active)
    in three cheap ``COUNT(*)`` queries.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected admin-stats query handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.

    Returns:
        ``200 OK`` with :class:`AdminStatsSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
    """
    await admin_auth.authenticate_admin(request)
    view = await interactor.run(GetAdminStatsQuery())
    return AdminStatsSchema.from_view(view)


class MetricPointSchema(BaseModel):
    """One day of a metric time series."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"day": "2026-05-26", "count": 12}]},
    )

    day: date = Field(
        description="UTC calendar day of the bucket.",
        examples=["2026-05-26"],
    )
    count: int = Field(
        description="Metric value for that day.",
        ge=0,
        examples=[12],
    )


class MetricSeriesSchema(BaseModel):
    """Dense daily series for one admin metric over the requested window."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "metric": "registrations",
                    "points": [
                        {"day": "2026-05-25", "count": 8},
                        {"day": "2026-05-26", "count": 12},
                    ],
                },
            ],
        },
    )

    metric: AdminMetric = Field(
        description="Which metric this series covers.",
        examples=[AdminMetric.REGISTRATIONS],
    )
    points: list[MetricPointSchema] = Field(
        description=(
            "One entry per day in the window, ascending by date. "
            "Days with no events are zero-filled, so the list always "
            "has exactly `days` entries."
        ),
    )

    @classmethod
    def from_result(cls, result: AdminMetricSeries) -> Self:
        return cls(
            metric=result.metric,
            points=[
                MetricPointSchema(day=point.day, count=point.count)
                for point in result.points
            ],
        )


_METRIC_PATH: Final = Path(
    description=(
        "Which metric series to return: `registrations`, "
        "`enrollments`, `active_users` (daily active users), or "
        "`new_products` (products created that day)."
    ),
    examples=["registrations"],
)


@router.get(
    "/metrics/{metric}",
    summary="Get a daily time series for an admin metric",
    operation_id="getAdminMetricSeries",
    response_model=MetricSeriesSchema,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def get_metric_series(
    request: Request,
    interactor: FromDishka[GetAdminMetricSeriesQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    metric: AdminMetric = _METRIC_PATH,
    days: int = Query(
        METRICS_DEFAULT_DAYS,
        ge=METRICS_MIN_DAYS,
        le=METRICS_MAX_DAYS,
        description=(
            "Length of the window in days, ending today (UTC), "
            f"`[{METRICS_MIN_DAYS}, {METRICS_MAX_DAYS}]` "
            "(`METRICS_MIN_DAYS` / `METRICS_MAX_DAYS`). "
            f"Defaults to {METRICS_DEFAULT_DAYS} "
            "(`METRICS_DEFAULT_DAYS`)."
        ),
        examples=[30],
    ),
) -> MetricSeriesSchema:
    """Return a zero-filled daily series for one dashboard metric.

    Admin-only. For the last ``days`` UTC days: ``registrations`` and
    ``enrollments`` are daily counts of the matching `statistics`
    events; ``active_users`` is distinct users with a ``site_visit``
    that day (the DAU series); ``new_products`` is products created that
    day (off ``products.created_at``, any status). The result always
    has exactly ``days`` points in ascending order, gaps zero-filled,
    so the SPA can chart it directly.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected metric-series query handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        metric: Which series to return (path enum).
        days: Window length in days ending today (UTC).

    Returns:
        ``200 OK`` with :class:`MetricSeriesSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
    """
    await admin_auth.authenticate_admin(request)
    result = await interactor.run(
        GetAdminMetricSeriesQuery(metric=metric, days=days),
    )
    return MetricSeriesSchema.from_result(result)


@router.get(
    "/users/search",
    summary="Search users (admin view, with ban status)",
    operation_id="searchUsersAdmin",
    response_model=list[AdminUserSummarySchema],
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def search_users_admin(
    request: Request,
    interactor: FromDishka[SearchUsersQueryHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    q: str = Query(
        description=(
            "Free-text query, whitespace-tokenized; each token must "
            "match (case-insensitive substring) at least one of "
            "`first_name` / `last_name` / `patronymic`. Empty input "
            "returns an empty list."
        ),
        min_length=0,
        max_length=200,
        examples=["Ada", "Иван Иванов"],
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset (rows to skip), `>= 0`.",
        examples=[0],
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Page size, `[1, {MAX_LIMIT}]` (`MAX_LIMIT`).",
        examples=[20],
    ),
) -> list[AdminUserSummarySchema]:
    """Search users by name, returning ban status for moderation.

    Admin-only. Identical matching/sorting to ``GET /users/search`` but
    the projection adds ``is_banned`` so the admin UI can offer a ban or
    an unban per result. The ban flag is deliberately kept off the
    public search/admins endpoints (see :class:`AdminUserSummarySchema`).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected user-search query handler (shared with the
            public search route — only the response projection differs).
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        q: Free-text query against name fields.
        offset: Pagination offset.
        limit: Page size.

    Returns:
        ``200 OK`` with a list of :class:`AdminUserSummarySchema`,
        possibly empty.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
    """
    await admin_auth.authenticate_admin(request)
    views = await interactor.run(
        SearchUsersQuery(
            query=q,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return [AdminUserSummarySchema.from_view(view) for view in views]


@router.post(
    "/users/{user_id}/ban",
    summary="Ban a user",
    operation_id="banUser",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def ban_user(
    request: Request,
    interactor: FromDishka[BanUserCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    user_id: UUID = _USER_ID_PATH,
) -> None:
    """Ban a user and revoke every active session they hold.

    Admin-only. Sets the user's ``is_banned`` flag (blocking future
    logins) and revokes all their refresh-token families so any
    access token already in their browser is rejected on the next
    request. Idempotent — re-banning re-revokes sessions opened
    since. There is no user-deletion counterpart by design.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected ban-user command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(BanUserCommand(user_id=UserID(user_id)))


@router.post(
    "/users/{user_id}/unban",
    summary="Lift a user's ban",
    operation_id="unbanUser",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def unban_user(
    request: Request,
    interactor: FromDishka[UnbanUserCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    user_id: UUID = _USER_ID_PATH,
) -> None:
    """Lift a user's ban so they can log in again.

    Admin-only and the inverse of ``POST /admin/users/{id}/ban``.
    Clears the ``is_banned`` flag; the user logs in afresh (the ban
    already revoked their sessions, so there is nothing to restore).
    Idempotent — unbanning a non-banned user is a no-op ``204``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected unban-user command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(UnbanUserCommand(user_id=UserID(user_id)))


@router.delete(
    "/notes/{note_id}",
    summary="Permanently delete a note",
    operation_id="adminDeleteNote",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def delete_note(
    request: Request,
    interactor: FromDishka[AdminDeleteNoteCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    note_id: UUID = _NOTE_ID_PATH,
) -> None:
    """Hard-delete a note regardless of status or ownership.

    Admin-only and **irreversible**. Unlike the author-facing
    ``DELETE /products/{id}`` (drafts only), this removes a note in
    any status — including published notes with enrollments. The
    delete cascades to every child row (modules, lessons, blocks,
    releases, enrollments, statistics, collaborations, roles, gifts,
    Q&A, tags, notifications) and erases the note's commercial
    history. Referenced files are soft-deleted from storage.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected admin delete-note command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        note_id: Target note product's UUID, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No note with the given id; HTTP 404.
    """
    ctx = await admin_auth.authenticate_admin(request)
    await interactor.run(
        AdminDeleteNoteCommand(
            actor_id=ctx.user_id,
            note_id=ProductID(note_id),
        ),
    )
