from typing import Final

PRESENCE_TTL_SECONDS: Final = 60
HEARTBEAT_INTERVAL_SECONDS: Final = 20

MAX_PRESENCE_SUBSCRIPTIONS: Final = 500
"""Hard cap on how many user-ids one presence WebSocket may track.

The subscribe message is otherwise unbounded — a client could send an
arbitrarily large ``user_ids`` array and grow the per-connection
subscription set without limit, inflating memory and the Redis
pipeline built on every ``filter_online``. Excess ids beyond this cap
are dropped."""
