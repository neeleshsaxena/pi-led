# pi-led

Plugin-based controller for the Raspberry Pi 64×64 HUB75 LED panel. **One
process owns the panel** and renders the currently-selected view; LED projects
are **plugins** that register their views. A small FastAPI web app provides the
admin (pick the active view, type a message) and a live preview.

Part of the Pi portfolio alongside [`match-day-live`](../../match-day-live).
This is the single panel owner ("Pattern A"): match-day-live keeps its web app,
but its LED rendering moves here as the `worldcup` plugin.

## Architecture

```
 Web app (controller.web)            Renderer (controller.runner)
 admin + preview, port 5070          single panel owner
        │  writes                            │  reads
        └────────►  .state.json  ◄───────────┘   (mtime-synced, no IPC)
                                              │
                              get_sink() ─────┤
                              PNGSink (dev) / HzellerSink (Pi)
```

- `pi_led_core/` — shared SDK: `canvas` (draw toolkit + 5×7 font), `matrix`
  (sinks + `get_sink()`), `plugin` (the `LedApp` contract + `RenderContext` +
  `ViewSpec`), `registry`, `state` (cross-process `ControllerState`).
- `apps/` — the plugins. Each is a package exposing a `LedApp`. Register it in
  `apps/__init__.py::ALL_APPS`.
  - `messages` — type a message in the admin; auto-fit, static, one view.
  - `worldcup` — World Cup today / next / standings (three views). *(porting)*
- `controller/` — the host: `web.py` (FastAPI app), `runner.py` (render loop).

### The plugin contract

A plugin subclasses `LedApp` and implements `render(ctx) -> Image`. It may
expose several admin-selectable views via `views()`, carry per-plugin config
(seeded by `default_config()`), and optionally contribute admin routes via
`admin_router()`. The active view is stored as `"<plugin>:<view>"` (e.g.
`worldcup:today`). Plugins never touch the sink and never assume they're the
only app on the panel.

## Run locally (Mac, PNG sink)

```bash
cd ~/workspace/pi-projects/pi-led
python3 -m venv .venv
.venv/bin/pip install -e .

# terminal 1 — renderer (writes /tmp/led-preview.png)
.venv/bin/python -m controller.runner

# terminal 2 — web app
.venv/bin/uvicorn controller.web:app --port 5070
```

Open <http://localhost:5070/admin> (admin / password printed on first run, or
set `ADMIN_PASSWORD`). Pick a view, type a message, watch the live preview.

## Add a new LED project

1. Create `apps/<name>/` with a `LedApp` subclass.
2. Append an instance to `ALL_APPS` in `apps/__init__.py`.
3. Done — its views appear in the admin automatically.

## Deploy

See [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Config (env vars)

| Var | Default | Controls |
|---|---|---|
| `PORT` | `5070` | Web app port |
| `ADMIN_PASSWORD` | auto → `.admin_password` | Admin login |
| `PI_LED_DEFAULT_ACTIVE` | `messages:main` | View on first run |
| `LED_FRAME_INTERVAL` | `0.2` | Seconds between frames |
| `LED_TRANSITION` | `0.5` | Crossfade seconds on view change (`0` off) |
| `LED_PREVIEW_PATH` | `/tmp/led-preview.png` | Dev PNG sink path |
| `LED_PREVIEW_SCALE` | `8` | PNG upscale for browser |
| `LED_SINK` | auto | `png` forces PNG sink even on Pi |
| `LED_GPIO_SLOWDOWN` | `2` | hzeller GPIO slowdown (Pi) |
| `LED_BRIGHTNESS` | `60` | hzeller brightness 0–100 (Pi) |
| `LED_DROP_PRIVS` | `0` | Pi: drop to `daemon` after init (`0`=stay root so renderer can read `.state.json`) |
| `LED_PI_PREVIEW` | `1` | Pi: also tee a throttled preview PNG (`0` disables) |
| `LED_PI_PREVIEW_INTERVAL` | `1.0` | Pi: seconds between preview frames |
