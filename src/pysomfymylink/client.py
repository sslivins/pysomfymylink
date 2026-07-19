"""Async client for the Somfy MyLink Synergy JSON-RPC socket API.

This is a clean-room rewrite of the transport layer that the original
``somfy-mylink-synergy`` library (by Ben Dews) got subtly wrong. The public
method surface is intentionally close to the original so it reads familiarly,
but the connection handling fixes two real defects:

1. **Deadlock on failure.** The original guarded its socket with a hand-rolled
   ``asyncio.Event`` "mutex" that was only reset on the happy path. Any connect
   timeout (common with a flaky hub) left the event cleared forever, so every
   later command blocked until Home Assistant was restarted. Here a real
   :class:`asyncio.Lock` is held with ``async with``, so it is *always*
   released — even on exceptions.

2. **Silent transport errors.** Connect/read failures now raise a typed
   :class:`~pysomfymylink.errors.SomfyMyLinkConnectionError` /
   :class:`~pysomfymylink.errors.SomfyMyLinkTimeoutError`, and JSON-RPC error
   replies raise :class:`~pysomfymylink.errors.SomfyMyLinkApiError`.

The hub only accepts one connection at a time and drops idle sockets, so a
fresh connection is opened per command and closed in a ``finally`` block.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import re
from typing import Any

from .const import ALL_TARGETS, DEFAULT_PORT, DEFAULT_TIMEOUT
from .errors import (
    SomfyMyLinkApiError,
    SomfyMyLinkConnectionError,
    SomfyMyLinkTimeoutError,
)
from .models import Shade

_LOGGER = logging.getLogger(__name__)

# The hub interleaves unsolicited {"keepalive":...} frames with real replies.
_KEEPALIVE_RE = re.compile(r'\{[^{}]*keepalive[^{}]*\}')


class SomfyMyLink:
    """Talk to a Somfy MyLink hub over its Synergy JSON-RPC socket."""

    def __init__(
        self,
        host: str,
        system_id: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Create a client. ``system_id`` is the hub's integration System ID."""
        self.host = host
        self.port = port
        self.system_id = system_id
        self.timeout = timeout
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)

    async def status_info(self, target_id: str = ALL_TARGETS) -> list[Shade]:
        """Return the covers configured on the hub."""
        result = await self._command("mylink.status.info", targetID=target_id)
        entries = result if isinstance(result, list) else []
        return [Shade.from_api(item) for item in entries]

    async def status_ping(self, target_id: str = ALL_TARGETS) -> Any:
        """Ping targets and return the raw hub result."""
        return await self._command("mylink.status.ping", targetID=target_id)

    async def move_up(self, target_id: str = ALL_TARGETS) -> Any:
        """Send a move-up command to ``target_id``."""
        return await self._command("mylink.move.up", targetID=target_id)

    async def move_down(self, target_id: str = ALL_TARGETS) -> Any:
        """Send a move-down command to ``target_id``."""
        return await self._command("mylink.move.down", targetID=target_id)

    async def move_stop(self, target_id: str = ALL_TARGETS) -> Any:
        """Send a stop/my command to ``target_id``."""
        return await self._command("mylink.move.stop", targetID=target_id)

    async def scene_list(self) -> Any:
        """List configured scenes."""
        return await self._command("mylink.scene.list")

    async def scene_run(self, scene_id: Any) -> Any:
        """Run the scene identified by ``scene_id``."""
        return await self._command("mylink.scene.run", sceneID=scene_id)

    async def _command(self, method: str, **params: Any) -> Any:
        """Build a JSON-RPC message, send it, and return its ``result``."""
        params.setdefault("auth", self.system_id)
        message_id = next(self._ids)
        message = {"id": message_id, "method": method, "params": params}
        response = await self._request(message, message_id)
        if "error" in response:
            error = response["error"] or {}
            raise SomfyMyLinkApiError(
                error.get("message", "Unknown MyLink error"),
                code=error.get("code"),
            )
        return response.get("result")

    async def _request(self, message: dict[str, Any], message_id: int) -> dict[str, Any]:
        """Open a socket, exchange one message, and always release the lock.

        The hub returns the request ``id`` as the last key, so we read until the
        ``"id":<n>}`` terminator, strip any interleaved keepalive frames, and
        parse the remaining JSON object.
        """
        terminator = b'"id":' + str(message_id).encode() + b"}"
        payload = json.dumps(message).encode()

        async with self._lock:
            reader, writer = await self._open()
            try:
                writer.write(payload)
                await writer.drain()
                raw = await asyncio.wait_for(
                    reader.readuntil(terminator), timeout=self.timeout
                )
            except TimeoutError as err:
                raise SomfyMyLinkTimeoutError(
                    f"Timed out waiting for a reply from {self.host}:{self.port}"
                ) from err
            except asyncio.IncompleteReadError as err:
                raise SomfyMyLinkConnectionError(
                    f"Connection to {self.host}:{self.port} closed mid-reply"
                ) from err
            except OSError as err:
                raise SomfyMyLinkConnectionError(
                    f"Socket error talking to {self.host}:{self.port}: {err}"
                ) from err
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

        return self._parse(raw)

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Open a TCP connection to the hub, translating failures to typed errors."""
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
        except TimeoutError as err:
            raise SomfyMyLinkTimeoutError(
                f"Timed out connecting to {self.host}:{self.port}"
            ) from err
        except OSError as err:
            raise SomfyMyLinkConnectionError(
                f"Unable to connect to {self.host}:{self.port}: {err}"
            ) from err

    @staticmethod
    def _parse(raw: bytes) -> dict[str, Any]:
        """Decode a hub reply, dropping keepalive frames, into a JSON object."""
        text = raw.decode("utf-8", errors="replace")
        text = _KEEPALIVE_RE.sub("", text).strip()
        start = text.find("{")
        if start > 0:
            text = text[start:]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            _LOGGER.debug("Undecodable MyLink reply: %r", raw)
            raise SomfyMyLinkConnectionError(
                "Could not decode reply from MyLink hub"
            ) from err
        if not isinstance(data, dict):
            raise SomfyMyLinkConnectionError("Unexpected non-object reply from MyLink hub")
        return data
