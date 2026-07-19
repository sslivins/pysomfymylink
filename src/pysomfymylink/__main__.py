"""Tiny CLI for manual smoke-testing pysomfymylink.

Usage:

    python -m pysomfymylink list                 # list configured covers
    python -m pysomfymylink up   <TARGET_ID>     # move a cover up
    python -m pysomfymylink down <TARGET_ID>     # move a cover down
    python -m pysomfymylink stop <TARGET_ID>     # stop / "my"

Connection details come from the environment (or a ``.env`` in the current
directory):

    SOMFY_MYLINK_HOST       hub IP / hostname
    SOMFY_MYLINK_SYSTEM_ID  the hub's integration System ID
    SOMFY_MYLINK_PORT       optional, defaults to 44100

``list`` is read-only. The move commands drive real motors, so use with care.
"""

from __future__ import annotations

import asyncio
import os
import sys

from .client import SomfyMyLink
from .const import DEFAULT_PORT


def _load_env() -> tuple[str, str, int]:
    host = os.environ.get("SOMFY_MYLINK_HOST")
    system_id = os.environ.get("SOMFY_MYLINK_SYSTEM_ID")
    if not (host and system_id):
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        host = os.environ.get("SOMFY_MYLINK_HOST")
        system_id = os.environ.get("SOMFY_MYLINK_SYSTEM_ID")
    if not (host and system_id):
        print(
            "Missing SOMFY_MYLINK_HOST / SOMFY_MYLINK_SYSTEM_ID in environment.",
            file=sys.stderr,
        )
        sys.exit(2)
    port = int(os.environ.get("SOMFY_MYLINK_PORT", DEFAULT_PORT))
    return host, system_id, port


async def _run(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    host, system_id, port = _load_env()
    client = SomfyMyLink(host, system_id, port=port)

    if cmd == "list":
        for shade in await client.status_info():
            print(f"{shade.target_id}\t{shade.name}\t(type={shade.cover_type})")
        return 0
    if cmd in ("up", "down", "stop") and rest:
        target = rest[0]
        action = {
            "up": client.move_up,
            "down": client.move_down,
            "stop": client.move_stop,
        }[cmd]
        await action(target)
        print(f"OK {cmd} {target}")
        return 0

    print(__doc__, file=sys.stderr)
    return 2


def main() -> None:  # pragma: no cover - entry point
    sys.exit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":  # pragma: no cover
    main()
