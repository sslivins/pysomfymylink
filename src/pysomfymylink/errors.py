"""Typed exception hierarchy for pysomfymylink."""

from __future__ import annotations


class SomfyMyLinkError(Exception):
    """Base class for all pysomfymylink errors."""


class SomfyMyLinkConnectionError(SomfyMyLinkError):
    """Raised when the MyLink hub is unreachable or the socket fails.

    Covers connection refused, host unreachable, connect timeouts, and any
    transport-level error while sending or receiving a message.
    """


class SomfyMyLinkTimeoutError(SomfyMyLinkConnectionError):
    """Raised when the hub accepts a connection but does not reply in time."""


class SomfyMyLinkApiError(SomfyMyLinkError):
    """Raised when the hub returns a JSON-RPC ``error`` object.

    :attr:`code` and :attr:`message` carry the hub's error payload. The most
    common cause is a bad System ID (the hub reports this as an auth error).
    """

    def __init__(self, message: str, *, code: int | None = None) -> None:
        self.code = code
        self.message = message
        super().__init__(message if code is None else f"[{code}] {message}")
