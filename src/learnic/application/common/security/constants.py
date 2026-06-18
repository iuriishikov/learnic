"""Fixed-in-code auth/security policy constants.

Knobs that are deliberately NOT environment-tunable (unlike the
per-environment values on ``SecurityConfig``). They live next to the
token/credential machinery in ``application/common/security`` because
they parameterize it; consumers are the auth command handlers
(``register``, ``resend_verification``).
"""

from typing import Final

VERIFY_EMAIL_TOKEN_TTL_SECONDS: Final = 60 * 60
"""Lifetime of a VERIFY email token, in seconds (1 hour).

Deliberately a fixed code constant rather than an env-tunable setting:
the verification window is a product decision, not a per-environment
operational knob. One source of truth — removes the env-vs-code drift
that once let prod silently run 24h while the code default said 1h.
"""
