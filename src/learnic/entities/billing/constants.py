from typing import Final

# Storage budget in bytes for the free tier — 2 GiB. Keep this an
# ``int`` expression: the value flows verbatim onto int-typed view /
# schema / WS-event fields (``storage_bytes_max``), and a float would
# leak ``2147483648.0`` over the storage WebSocket channels.
FREE_PLAN_STORAGE_BYTES: Final = 2 * 1024 * 1024 * 1024
# Storage budget in bytes for the BETA tier — 50 GiB. Assigned
# manually until the payment integration lands.
BETA_PLAN_STORAGE_BYTES: Final = 50 * 1024 * 1024 * 1024

# Plan code column width in the ``subscriptions`` table. Generous
# enough to absorb future plan additions ("PREMIUM", "TEAM_SEAT_5")
# without a migration.
PLAN_CODE_MAX_LEN: Final = 32

# How long an over-quota author keeps their excess files before
# the reconciliation job soft-deletes the overflow. Counted from
# the moment the breach was first detected. Shrink only after
# product confirms the new value — the SPA copy ("you have N days
# to free up X GB") references this constant.
OVER_QUOTA_GRACE_PERIOD_DAYS: Final = 14

# Minimum interval between successive "you are over quota"
# notifications for the same user. Prevents the daily reconcile
# job from spamming an inbox while the breach persists. Resets
# when the breach is resolved (user freed up space or upgraded)
# so a re-occurrence after fix-then-overrun is announced promptly.
OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS: Final = 3
