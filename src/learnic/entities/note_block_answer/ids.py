import uuid
from typing import NewType

# Stable identity for one persisted learner submission against an
# interactive release block. One row per (student, release block) —
# resubmitting overwrites the same row, so the id stays stable across
# re-answers. Generated in the domain via ``uuid.uuid4()`` inside
# :meth:`NoteBlockAnswer.record`, never by the DB.
NoteBlockAnswerID = NewType("NoteBlockAnswerID", uuid.UUID)
