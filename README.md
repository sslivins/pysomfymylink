# pysomfymylink

An async Python client for the **Somfy MyLink** "Synergy" JSON-RPC socket API
(the local TCP interface on port `44100` exposed by the Somfy MyLink /
`SomfyRtsBridge` hub).

This is a maintained, clean-room rewrite of the excellent but now unmaintained
[`somfy-mylink-synergy`](https://github.com/bendews/somfy-mylink-synergy) by
**Ben Dews** (last released 2019). Full credit to Ben for the original API
design and protocol reverse-engineering. This rewrite keeps a familiar method
surface but reimplements the transport layer to fix two real defects:

- **No more deadlock on a flaky hub.** The original used an `asyncio.Event` as
  a mutex that was not released on the connect-timeout path, so after a single
  connection timeout *every* subsequent command blocked forever until Home
  Assistant was restarted. This version guards the socket with a real
  `asyncio.Lock` held via `async with`, so it is always released — even on
  errors.
- **Typed errors.** Transport failures raise `SomfyMyLinkConnectionError` /
  `SomfyMyLinkTimeoutError`; JSON-RPC error replies raise `SomfyMyLinkApiError`.

## Install

```bash
pip install pysomfymylink
```

No runtime dependencies — the client uses only the stdlib `asyncio` socket API.

## Usage

```python
import asyncio
from pysomfymylink import SomfyMyLink

async def main():
    hub = SomfyMyLink("192.168.1.10", "your-system-id")

    for shade in await hub.status_info():
        print(shade.target_id, shade.name, shade.cover_type)

    await hub.move_up("<TARGET_ID>")
    await hub.move_down("<TARGET_ID>")
    await hub.move_stop("<TARGET_ID>")   # stop / "my" favorite

asyncio.run(main())
```

The **System ID** is found in the MyLink mobile app under *Integration* →
select any non-Cloud service.

### CLI

```bash
export SOMFY_MYLINK_HOST=192.168.1.10
export SOMFY_MYLINK_SYSTEM_ID=your-system-id
python -m pysomfymylink list            # read-only
python -m pysomfymylink up   <TARGET_ID>
python -m pysomfymylink stop <TARGET_ID>
```

## API

| Method | Description |
| --- | --- |
| `status_info(target_id="*.*")` | List configured covers as `Shade` objects |
| `status_ping(target_id="*.*")` | Ping targets |
| `move_up / move_down / move_stop(target_id)` | Drive a cover |
| `scene_list()` / `scene_run(scene_id)` | List / run scenes |

## Notes / limitations

Somfy RTS is a **one-way** radio protocol: the hub cannot report a cover's real
position, so consumers must treat state as *assumed*. A `move_stop` on a
stationary cover can send it to its configured "my" favorite position.

## License

MIT. See [LICENSE](LICENSE), which preserves credit to the original author.
