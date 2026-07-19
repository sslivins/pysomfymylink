"""Shared fixtures: a fake in-process MyLink hub speaking the Synergy protocol."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest

from pysomfymylink import SomfyMyLink

# Two covers the fake hub reports from mylink.status.info.
FAKE_SHADES = [
    {"targetID": "CE1A2B3C.1", "name": "Left Shade", "type": 0},
    {"targetID": "CE1A2B3C.2", "name": "Right Shade", "type": 1},
]


@dataclass
class FakeHub:
    """A minimal asyncio TCP server that mimics a Somfy MyLink hub."""

    host: str
    port: int
    server: asyncio.AbstractServer
    client: SomfyMyLink
    # Records every method the hub was asked to run, for assertions.
    calls: list[str] = field(default_factory=list)
    # When True, prepend an unsolicited keepalive frame to the next reply.
    send_keepalive: bool = False
    # Reply with non-JSON garbage (still terminated) to exercise parse errors.
    corrupt: bool = False
    # Accept the connection but never reply, to exercise the read timeout.
    silent: bool = False

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        data = await reader.read(4096)
        if not data:
            writer.close()
            return
        msg = json.loads(data.decode())
        mid = msg["id"]
        method = msg["method"]
        self.calls.append(method)
        auth = msg.get("params", {}).get("auth")

        if self.silent:
            # Wait for the client to give up and close, so teardown is prompt.
            await reader.read()
            writer.close()
            return
        if self.corrupt:
            writer.write(b'not-json"id":' + str(mid).encode() + b"}")
            await writer.drain()
            writer.close()
            return
        if auth == "bad":
            resp = {"error": {"code": 4, "message": "Invalid System ID"}, "id": mid}
        elif method == "mylink.status.info":
            resp = {"result": FAKE_SHADES, "id": mid}
        else:
            resp = {"result": True, "id": mid}

        # The real hub emits compact JSON with "id" last; match that so the
        # client's `"id":<n>}` terminator is found.
        out = json.dumps(resp, separators=(",", ":")).encode()
        if self.send_keepalive:
            out = json.dumps({"keepalive": True}, separators=(",", ":")).encode() + out
        writer.write(out)
        await writer.drain()
        writer.close()


@pytest.fixture
async def fake_hub() -> AsyncIterator[FakeHub]:
    """Start a fake hub on a random loopback port and hand back a wired client."""
    hub_ref: dict[str, FakeHub] = {}

    async def handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await hub_ref["hub"]._handle(reader, writer)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = SomfyMyLink("127.0.0.1", "good-system-id", port=port, timeout=2.0)
    hub = FakeHub(host="127.0.0.1", port=port, server=server, client=client)
    hub_ref["hub"] = hub

    yield hub

    server.close()
    await server.wait_closed()


@pytest.fixture
def unused_tcp_port() -> int:
    """A loopback port with nothing listening (connections are refused)."""
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
