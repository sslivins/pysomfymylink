"""Unit tests for the pysomfymylink client against a fake in-process hub."""

from __future__ import annotations

import pytest

from pysomfymylink import (
    Shade,
    SomfyMyLink,
    SomfyMyLinkApiError,
    SomfyMyLinkConnectionError,
    SomfyMyLinkTimeoutError,
)

from .conftest import FakeHub

pytestmark = pytest.mark.unit


async def test_status_info_parses_shades(fake_hub: FakeHub) -> None:
    shades = await fake_hub.client.status_info()
    assert [s.target_id for s in shades] == ["CE1A2B3C.1", "CE1A2B3C.2"]
    assert shades[0] == Shade(
        target_id="CE1A2B3C.1",
        name="Left Shade",
        cover_type=0,
        raw={"targetID": "CE1A2B3C.1", "name": "Left Shade", "type": 0},
    )
    assert shades[1].cover_type == 1
    assert fake_hub.calls == ["mylink.status.info"]


@pytest.mark.parametrize(
    ("action", "method"),
    [
        ("move_up", "mylink.move.up"),
        ("move_down", "mylink.move.down"),
        ("move_stop", "mylink.move.stop"),
    ],
)
async def test_move_commands_send_expected_method(
    fake_hub: FakeHub, action: str, method: str
) -> None:
    result = await getattr(fake_hub.client, action)("CE1A2B3C.1")
    assert result is True
    assert fake_hub.calls == [method]


async def test_default_target_is_wildcard(fake_hub: FakeHub) -> None:
    await fake_hub.client.move_up()
    assert fake_hub.calls == ["mylink.move.up"]


async def test_keepalive_frames_are_stripped(fake_hub: FakeHub) -> None:
    fake_hub.send_keepalive = True
    shades = await fake_hub.client.status_info()
    assert len(shades) == 2


async def test_api_error_raises(fake_hub: FakeHub) -> None:
    fake_hub.client.system_id = "bad"
    with pytest.raises(SomfyMyLinkApiError) as excinfo:
        await fake_hub.client.status_info()
    assert excinfo.value.code == 4
    assert "System ID" in excinfo.value.message


async def test_connection_refused_raises_typed_error(unused_tcp_port: int) -> None:
    client = SomfyMyLink("127.0.0.1", "sid", port=unused_tcp_port, timeout=1.0)
    with pytest.raises(SomfyMyLinkConnectionError):
        await client.move_up("T1")
    # Regression guard: the lock must be released after a transport failure.
    assert client._lock.locked() is False


async def test_no_deadlock_after_failed_connection(fake_hub: FakeHub) -> None:
    """Reproduce the original bug: a failed attempt must not wedge later calls.

    The legacy library left its mutex permanently acquired after any connect
    failure, so the *next* command blocked forever. We force one failure, then
    assert the very next command against the working hub succeeds.
    """
    client = fake_hub.client
    real_open = client._open
    attempts = {"n": 0}

    async def flaky_open():  # type: ignore[no-untyped-def]
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise SomfyMyLinkTimeoutError("forced connect timeout")
        return await real_open()

    client._open = flaky_open  # type: ignore[method-assign]

    with pytest.raises(SomfyMyLinkTimeoutError):
        await client.move_up("CE1A2B3C.1")

    assert client._lock.locked() is False

    shades = await client.status_info()
    assert [s.target_id for s in shades] == ["CE1A2B3C.1", "CE1A2B3C.2"]


async def test_message_ids_increment(fake_hub: FakeHub) -> None:
    first = next(fake_hub.client._ids)
    second = next(fake_hub.client._ids)
    assert second == first + 1


async def test_status_ping_returns_raw_result(fake_hub: FakeHub) -> None:
    result = await fake_hub.client.status_ping()
    assert result is True
    assert fake_hub.calls == ["mylink.status.ping"]


async def test_scene_list_and_run(fake_hub: FakeHub) -> None:
    await fake_hub.client.scene_list()
    await fake_hub.client.scene_run(7)
    assert fake_hub.calls == ["mylink.scene.list", "mylink.scene.run"]


async def test_corrupt_reply_raises_connection_error(fake_hub: FakeHub) -> None:
    fake_hub.corrupt = True
    with pytest.raises(SomfyMyLinkConnectionError):
        await fake_hub.client.status_info()
    assert fake_hub.client._lock.locked() is False


async def test_read_timeout_raises_timeout_error(fake_hub: FakeHub) -> None:
    fake_hub.silent = True
    fake_hub.client.timeout = 0.3
    with pytest.raises(SomfyMyLinkTimeoutError):
        await fake_hub.client.status_info()
    assert fake_hub.client._lock.locked() is False
