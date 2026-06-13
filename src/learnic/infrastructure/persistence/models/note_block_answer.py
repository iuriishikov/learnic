"""``note_block_answers`` table — persisted learner submissions.

One row per ``(student, release block)``: a logged-in learner's
*latest* answer to an interactive block, kept so the SPA can restore
their selection + verdict on reload. The row is upserted on the
``uq_note_block_answers_user_block`` unique constraint.

The table is intentionally **not** imperatively mapped — the
polymorphic ``submission`` lives in a single ``JSONB`` column, so the
gateway/reader use Core statements with explicit (de)serialisation,
the same approach as the release-block subtype tables and
``enrollment_note_details``. No ``map_*`` function is needed because
nothing is ORM-mapped, and there is no ``map_note_block_answer_table``
entry in ``setup_map_tables`` for the same reason.

Schema lifecycle in this codebase is migration-driven, not metadata
-driven: the table is created in the DB by the hand-written migration
``nbansw0001`` (columns inlined there), and reaches the running Python
process via the import chain ``adapters/note_block_answer`` ->
``ioc`` so the Core statements can reference the ``sa.Table`` object.
This ``sa.Table`` IS registered on ``mapper_registry.metadata`` like
every other table, and ``alembic/env.py`` now imports every ``models/*``
submodule, so it is part of ``target_metadata`` and autogenerate would
see it. Migrations remain hand-written by convention, but autogenerate
is no longer dangerously blind to this (or any) table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from learnic.infrastructure.persistence.models.registry import (
    mapper_registry,
)

note_block_answers_table = sa.Table(
    "note_block_answers",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "block_id",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("note_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("is_correct", sa.Boolean(), nullable=False),
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
    sa.UniqueConstraint(
        "user_id",
        "block_id",
        name="uq_note_block_answers_user_block",
    ),
    sa.Index(
        "ix_note_block_answers_user_release",
        "user_id",
        "release_id",
    ),
)
