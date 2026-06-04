import uuid
from typing import NewType

LessonBlockID = NewType("LessonBlockID", uuid.UUID)

# Stable identity for one option inside a single- or multi-choice block.
# Indices won't do — authors reorder/delete options after creation, and
# ``correct_option_id`` must continue pointing at the same answer through
# every edit. New ids are generated in the domain via ``uuid.uuid4()``
# inside the option factory, never by the DB.
ChoiceOptionID = NewType("ChoiceOptionID", uuid.UUID)

# Stable identity for one photo inside a :class:`PhotoCollageBlock`.
# Required so granular item operations (add / remove / reorder /
# caption edit) can address a single photo by id without relying on
# the array index, which shifts under reorder. New ids are generated
# in the domain via ``uuid.uuid4()`` inside the block's mutation
# methods, never by the DB.
CollageItemID = NewType("CollageItemID", uuid.UUID)
