"""Administrative command-line interface.

``grant-admin`` promotes a user to platform administrator by UUID — the
only way to mint an admin (there is intentionally no HTTP route for it,
since that would be a privilege-escalation hole).

Run via the console script (after ``poetry install`` registers it)::

    poetry run grant-admin <user-uuid>

or directly as a module without reinstalling::

    poetry run python -m learnic.cli <user-uuid>

It boots the same dishka container the API uses, so it shares the
exact gateways, transaction handling, and config — there is no second
code path that could drift from the application's invariants.

Output goes through ``rich`` (``_out`` / ``_err`` consoles) so future
admin commands share one styled, colour-aware surface; user-supplied
text is always passed through :func:`rich.markup.escape` so a stray
``[`` cannot be interpreted as console markup.
"""

import argparse
import asyncio
import uuid
from typing import Final

from rich.console import Console
from rich.markup import escape

from learnic.application.commands.admin.grant_admin import (
    GrantAdminCommand,
    GrantAdminCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.bootstrap import setup_configs, setup_map_tables
from learnic.entities.user.models import UserID
from learnic.ioc import setup_providers

_out: Final = Console()
_err: Final = Console(stderr=True)


async def _grant_admin(user_id: UserID) -> None:
    setup_map_tables()
    container = setup_providers(setup_configs())
    try:
        async with container() as request_container:
            handler = await request_container.get(GrantAdminCommandHandler)
            await handler.run(GrantAdminCommand(user_id=user_id))
    finally:
        await container.close()


def grant_admin_main(argv: list[str] | None = None) -> int:
    """Promote a user to platform administrator by UUID.

    Returns:
        Process exit code: ``0`` on success, ``1`` when the target
        user does not exist, ``2`` on a malformed UUID argument.
    """
    parser = argparse.ArgumentParser(
        prog="grant-admin",
        description="Promote a user to platform administrator by UUID.",
    )
    parser.add_argument(
        "user_id",
        help="UUID of the user to promote.",
    )
    args = parser.parse_args(argv)
    raw_id = escape(args.user_id)

    try:
        user_id = UserID(uuid.UUID(args.user_id))
    except ValueError:
        _err.print(f"[bold red]✗[/] '{raw_id}' is not a valid UUID")
        return 2
    try:
        asyncio.run(_grant_admin(user_id))
    except EntityNotFoundError:
        _err.print(f"[bold red]✗[/] no user with id [bold]{raw_id}[/]")
        return 1
    _out.print(f"[bold green]✓[/] granted admin to [bold]{raw_id}[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(grant_admin_main())
