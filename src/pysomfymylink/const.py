"""Public constants for the Somfy MyLink Synergy JSON-RPC API.

These identify the on-hub Synergy socket API, not any particular user, and
are the same for every MyLink device. They are not secrets.
"""

from __future__ import annotations

# TCP port the MyLink Synergy JSON-RPC socket listens on.
DEFAULT_PORT: int = 44100

# Per-command timeout (seconds) for both connecting and reading a reply.
# The hub is single-connection and can take ~1-2s to answer status.info,
# so keep a comfortable default.
DEFAULT_TIMEOUT: float = 5.0

# Wildcard target that addresses every configured cover/motor.
ALL_TARGETS: str = "*.*"
