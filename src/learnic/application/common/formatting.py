"""Public-facing display helpers shared by query handlers and schemas.

The two functions in this module are the canonical way the API exposes
user identities outside the account owner:

- :func:`build_full_name` collapses the ``last_name`` /
  ``first_name`` / ``patronymic`` triple into a single string in the
  Russian-style "Last First Patronymic" order so the SPA can render a
  user's display name without re-implementing the join in every
  callsite.
- :func:`mask_email` turns a raw address into a privacy-respecting
  ``f*****d@domain.com`` shape so the API never returns plain emails
  in user-facing read projections.

Both helpers are pure — no I/O, no domain rules — which is why they
live under ``application/common/`` rather than in ``entities/``: VOs
own *invariants*, while these helpers own *presentation*.
"""

from typing import Final

_LOCAL_MASK: Final = "*****"


def build_full_name(
    first_name: str,
    last_name: str,
    patronymic: str | None,
) -> str:
    """Return the user's display name as ``Last First Patronymic``.

    Empty / whitespace-only parts are dropped so a missing patronymic
    yields ``"Last First"``. Output is trimmed; never returns ``None``.
    """
    parts = (last_name, first_name, patronymic)
    return " ".join(p.strip() for p in parts if p and p.strip())


def mask_email(email: str) -> str:
    """Return ``email`` with the local part masked to ``f*****d``.

    The first and last characters of the local part are preserved so
    the user can still recognise their own address; everything in
    between collapses to a fixed-length asterisk run. The domain is
    left intact. Inputs without ``@`` are masked as a single local
    part with no domain suffix; that branch should not happen in
    practice — the domain ``Email`` VO rejects such values — but the
    helper stays defensive so callers do not need to special-case
    bad data.
    """
    at = email.rfind("@")
    if at == -1:
        return _mask_local(email)
    local = email[:at]
    domain = email[at:]
    return f"{_mask_local(local)}{domain}"


def _mask_local(local: str) -> str:
    if len(local) == 0:
        return _LOCAL_MASK
    if len(local) == 1:
        return f"{local}{_LOCAL_MASK}"
    return f"{local[0]}{_LOCAL_MASK}{local[-1]}"
