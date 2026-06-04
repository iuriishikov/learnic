"""Event envelope alias for the note-content collaboration channel.

The channel rides on the generic
:class:`~learnic.application.common.events.Event` envelope; this
module fixes ``TPayload`` to the channel-specific
:data:`~learnic.application.common.collaboration.payloads.ContentPayload`
union so the rest of the code reads as
``ContentEvent`` instead of ``Event[ContentPayload]`` at every
use site.
"""

from typing import TypeAlias

from learnic.application.common.collaboration.payloads import ContentPayload
from learnic.application.common.events import Event

ContentEvent: TypeAlias = Event[ContentPayload]
