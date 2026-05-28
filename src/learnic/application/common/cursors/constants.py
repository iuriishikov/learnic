from typing import Final

# Stale-cursor threshold. A cursor whose ``last_seen`` is older
# than this is treated as gone — the snapshot endpoint prunes it
# inline before returning. The client carries its own ~15-second
# eviction timer, so this only needs to be loose enough to absorb
# brief network hiccups; it does not gate user-visible cleanup.
CURSOR_STALE_SECONDS: Final = 30

# Wire-level hygiene caps. ``field_id`` and ``action`` are opaque
# strings on the server (the frontend owns the taxonomy), so the
# only validation is "don't accept arbitrarily large payloads."
FIELD_ID_MAX_LEN: Final = 256
ACTION_MAX_LEN: Final = 64
