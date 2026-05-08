from typing import Final

ROLE_NAME_MIN_LEN: Final = 1
ROLE_NAME_MAX_LEN: Final = 100

ROLE_DESCRIPTION_MAX_LEN: Final = 1_000

# Role hierarchy positions — Discord-style. Lower number = higher in
# the chain. ``OWNER_POSITION`` is synthetic: the product author has no
# row in ``roles`` but always outranks every role.
OWNER_POSITION: Final = 0
ROLE_POSITION_MIN: Final = 1
ROLE_POSITION_MAX: Final = 1_000_000

# System-role default positions. Spaced so future system roles can
# slot between them without renumbering. Higher number = lower rank.
MODERATOR_POSITION: Final = 100
EDITOR_POSITION: Final = 200
COMMENTOR_POSITION: Final = 300
VIEWER_POSITION: Final = 400
