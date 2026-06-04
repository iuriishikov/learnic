"""Shared SQL helpers for embedding a unified user projection in a row.

The API exposes a single ``UserSchema`` wherever a user is embedded in a
parent resource — product author, gift gifter/recipient, collaboration
collaborator, notification actor, … (see the unification in
``presentation/http/common/schemas.py``). On the read side that means
every such adapter must SELECT the same identity + avatar/cover columns
and rebuild the same :class:`UserView`. These helpers are the single
source of truth for that column set and row→view mapping so the
embeddings cannot drift apart.

Convention: a caller picks a ``prefix`` per embedded user (``"author"``,
``"gifter"``, ``"recipient"``, ``"collaborator"``, ``"actor"``) and uses
it for both the SELECT (``embedded_user_columns``) and the row read
(``user_view_from_row`` / ``user_view_from_row_optional``). The avatar
and cover file columns are nested under ``{prefix}_avatar_*`` /
``{prefix}_cover_*``.

Profile-only fields (``description`` / ``website_url`` /
``portfolio_url`` / ``public_email``) are intentionally ``None`` here:
an embedded user carries identity + media, never the full profile —
that lives at ``GET /users/{id}``.
"""

from typing import Any

import sqlalchemy as sa

from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.user import UserView
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


def _file_alias_columns(
    alias: sa.FromClause,
    prefix: str,
) -> list[sa.ColumnElement[Any]]:
    """Return the five ``{prefix}_*`` labelled columns for a file alias."""
    return [
        alias.c.oid.label(f"{prefix}_oid"),
        alias.c.storage_name.label(f"{prefix}_storage_name"),
        alias.c.bucket.label(f"{prefix}_bucket"),
        alias.c.content_type.label(f"{prefix}_content_type"),
        alias.c.size_bytes.label(f"{prefix}_size_bytes"),
    ]


def _file_meta_from_row(row: sa.Row[Any], prefix: str) -> FileMeta | None:
    """Build a :class:`FileMeta` from ``{prefix}_*`` columns, or ``None``.

    ``None`` when the aliased file was absent (``LEFT JOIN`` miss /
    soft-deleted), keyed off the always-present ``{prefix}_oid`` column.
    """
    oid = getattr(row, f"{prefix}_oid")
    if oid is None:
        return None
    return FileMeta(
        oid=FileID(oid),
        storage_name=getattr(row, f"{prefix}_storage_name"),
        bucket=getattr(row, f"{prefix}_bucket"),
        content_type=getattr(row, f"{prefix}_content_type"),
        size_bytes=getattr(row, f"{prefix}_size_bytes"),
    )


def file_columns(alias: sa.FromClause, prefix: str) -> list[sa.ColumnElement[Any]]:
    """Public re-export of :func:`_file_alias_columns` for standalone file aliases.

    Used for non-embedded-user file columns on the same row (e.g. a
    product's own cover), so a single adapter keeps one column-labelling
    convention for every file it joins.
    """
    return _file_alias_columns(alias, prefix)


def file_from_row(row: sa.Row[Any], prefix: str) -> FileMeta | None:
    """Public re-export of :func:`_file_meta_from_row` for standalone files."""
    return _file_meta_from_row(row, prefix)


def embedded_user_columns(
    user_alias: sa.FromClause,
    avatar_alias: sa.FromClause,
    cover_alias: sa.FromClause,
    prefix: str,
) -> list[sa.ColumnElement[Any]]:
    """Identity + avatar/cover columns for one embedded user.

    ``user_alias`` is the joined ``users`` row (or an ``aliased`` copy
    when a query embeds two users — gifter and recipient); the two file
    aliases are LEFT-joined ``files`` rows for the user's avatar/cover.
    """
    return [
        user_alias.c.oid.label(f"{prefix}_oid"),
        user_alias.c.email.label(f"{prefix}_email"),
        user_alias.c.first_name.label(f"{prefix}_first_name"),
        user_alias.c.last_name.label(f"{prefix}_last_name"),
        user_alias.c.patronymic.label(f"{prefix}_patronymic"),
        user_alias.c.is_verified.label(f"{prefix}_is_verified"),
        *_file_alias_columns(avatar_alias, f"{prefix}_avatar"),
        *_file_alias_columns(cover_alias, f"{prefix}_cover"),
    ]


def user_view_from_row(row: sa.Row[Any], prefix: str) -> UserView:
    """Rebuild a :class:`UserView` from ``{prefix}_*`` columns.

    Use for a **required** embedded user (the row is guaranteed present —
    e.g. a product author or a gift gifter). For a nullable embedded user
    behind an outer join, use :func:`user_view_from_row_optional`.
    """
    return UserView(
        oid=UserID(getattr(row, f"{prefix}_oid")),
        email=getattr(row, f"{prefix}_email"),
        first_name=getattr(row, f"{prefix}_first_name"),
        last_name=getattr(row, f"{prefix}_last_name"),
        patronymic=getattr(row, f"{prefix}_patronymic"),
        is_verified=getattr(row, f"{prefix}_is_verified"),
        description=None,
        avatar=_file_meta_from_row(row, f"{prefix}_avatar"),
        cover=_file_meta_from_row(row, f"{prefix}_cover"),
        website_url=None,
        portfolio_url=None,
        public_email=None,
    )


def user_view_from_row_optional(
    row: sa.Row[Any],
    prefix: str,
) -> UserView | None:
    """Same as :func:`user_view_from_row`, but ``None`` for an absent join.

    Keyed off ``{prefix}_oid`` — ``None`` means the outer join missed
    (an email-only gift recipient or collaboration invite with no
    registered user row yet).
    """
    if getattr(row, f"{prefix}_oid") is None:
        return None
    return user_view_from_row(row, prefix)
