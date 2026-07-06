# pi-led

A plugin-based controller that drives a **Raspberry Pi + 64×64 HUB75 RGB LED panel**.
One process owns the panel; every "app" is an in-process plugin that registers one or
more views. A built-in **carousel** rotates through them, so the panel cycles through
live World Cup scores and a knockout bracket, weather, a dual‑timezone clock, scrolling
messages, and ambient eye‑candy — all on a 64×64 grid.

Built end-to-end with [Claude Code](https://claude.com/claude-code): hardware bring-up,
the rendering engine, and every app.

<!-- Add a photo/GIF of the panel here. -->

---

## Contents
- [What it does](#what-it-does)
- [Hardware](#hardware)
- [Assembly & the one required solder joint](#assembly--the-one-required-solder-joint)
- [Software setup (Raspberry Pi)](#software-setup-raspberry-pi)
- [Architecture](#architecture)
- [The apps we built](#the-apps-we-built)
- [Running it](#running-it)
- [Writing your own app (plugin)](#writing-your-own-app-plugin)
- [Repo layout](#repo-layout)

---

## What it does

The panel is a shared display. Instead of one program hard-coding what to show, a single
**renderer** owns the panel and asks whichever **plugin** is active for the next frame. A
**carousel** plugin drives an automatic rotation, and a small web app lets you preview the
panel live and switch views from your phone.

Apps currently in the rotation:

| App | Views |
|-----|-------|
| **World Cup** | today's matches, next fixtures, a **knockout bracket** (a converging tree with flags), full-time/live scores with scorers & penalty-shootout results, group standings |
| **Weather** | current conditions + short forecast (Open-Meteo, no API key) |
| **Clock** | dual-timezone digital + an analog face |
| **Messages** | a scrolling/animated message you set from the web UI |
| **Ambient** | plasma, fire, "matrix" rain, starfield, Conway's Life |
| **Carousel** | rotates through a configurable list of the views above |

---

## Hardware

Everything is off-the-shelf. The exact parts used here:

| Part | Notes |
|------|-------|
| **Raspberry Pi** | A Pi 3B was used; any modern Pi with the 40-pin header works. |
| **RGB Matrix Bonnet** (Adafruit #3211) | HAT that drives HUB75 panels from the Pi's GPIO. Includes a level shifter and a barrel jack for panel power. |
| **64×64 RGB LED panel, P3 (3 mm pitch), HUB75** (e.g. Adafruit #4732) | The display itself. |
| **5 V / 4 A power supply** | Powers the panel through the Bonnet's barrel jack. A 64×64 panel at full white can pull several amps — don't under-spec this. |
| **IDC ribbon cable + panel power cable** | Usually ship with the panel: ribbon carries HUB75 data, the power pigtail feeds the panel. |
| Soldering iron + solder | For the one jumper below. |

> Power the **panel** from the 5 V supply via the Bonnet — do **not** try to run a 64×64
> panel off the Pi's 5 V pins.

---

## Assembly & the one required solder joint

1. **Seat the Bonnet** on the Pi's 40-pin header.
2. **Solder the `E`↔`8` address jumper on the Bonnet.** This is *mandatory* for 64×64
   panels. 32-pixel-tall panels use address lines A–D; a 64-pixel-tall panel needs a 5th
   line (`E`), and the Adafruit Bonnet leaves you to pick which GPIO it maps to by bridging
   a pair of pads. Bridge **`E` to `8`** (GPIO 8) and match that in the renderer config
   (`hardware_mapping = adafruit-hat`). Without this bridge the bottom half of the panel is
   scrambled. *(This was the single "gotcha" of the whole build — nothing else needs
   soldering.)*
3. **Connect the ribbon** from the Bonnet to the panel's HUB75 **input** (chained panels
   have an in/out — use IN), and the **power pigtail** from the Bonnet's screw terminals to
   the panel.
4. **Plug the 5 V PSU** into the Bonnet's barrel jack.

---

## Software setup (Raspberry Pi)

### 1. Disable on-board audio
The Pi's audio and the panel's PWM both want the same hardware timers, and the conflict
causes visible flicker. Blacklist the sound module:

```bash
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
sudo update-initramfs -u && sudo reboot
```

### 2. Build the panel driver (hzeller rpi-rgb-led-matrix)
The panel is driven by [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix),
built from source. Its Python bindings use a modern scikit-build/CMake build:

```bash
sudo apt-get install -y cmake
git clone https://github.com/hzeller/rpi-rgb-led-matrix
cd rpi-rgb-led-matrix
pip install --no-build-isolation .     # builds the `rgbmatrix` Python module
```

pi-led's sink auto-detects this module: if `rgbmatrix` imports, it drives the real panel;
otherwise it writes a preview PNG (so the exact same code runs on a laptop).

### 3. Install pi-led
```bash
git clone <this-repo> pi-led && cd pi-led
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

### 4. Panel config (what worked here)
`hardware_mapping=adafruit-hat`, `rows=64`, `cols=64`, `chain=1`, `gpio_slowdown=2`,
`brightness≈60`, `drop_privileges=0` (the renderer runs as root to read its state file and
to get the timing it needs). If your panel shows tearing, nudge `gpio_slowdown`.

### 5. Run as services
Two `systemd` units (see `deploy/`): a **renderer** (owns the panel, runs as root) and a
**web** app (admin + live preview). Optionally put the web app behind a reverse proxy with
an mDNS alias so you can reach it at something like `http://ledpanel.local/` on your LAN.

> The deploy scripts read the Pi host from a `PI_HOST` env var (default
> `pi@raspberrypi.local`) — set it to your Pi. Nothing else is machine-specific.

---

## Architecture

Two processes, **no IPC** — they sync through one JSON file's modification time:

```
 Web app (controller.web, uvicorn)          Renderer (controller.runner)
 admin + live preview                        single panel owner, render loop
        │  writes active view / config              │  reads it (mtime-synced)
        └──────────────►  .state.json  ◄────────────┘
                                                     │
                                     get_sink() ─────┤
                       PNGSink (dev)  ·  HzellerSink (panel)  ·  TeeSink (panel + PNG mirror)
```

- **Only the renderer touches the panel.** Plugins never touch the hardware and never
  assume they're the only app, so brightness, cross-fades and scheduling live in one place.
- `get_sink()` **auto-detects** the environment — real panel on the Pi, preview PNG on a
  laptop. `TeeSink` can mirror the panel to a throttled PNG so you can watch it remotely.
- `ControllerState` holds `{active, configs}` in `.state.json`; the web app writes it, the
  renderer polls its mtime. Same lightweight pattern top to bottom — no message bus.

Each plugin implements the small **`LedApp`** contract (`pi_led_core/plugin.py`):

```python
class LedApp:
    id: str
    name: str
    def views(self) -> list[ViewSpec]: ...          # one or more selectable views
    def default_config(self) -> dict: ...            # seed config the admin can edit
    async def render(self, ctx) -> Image.Image: ...  # return one 64×64 RGB frame
    async def start(self) / aclose(self): ...        # optional client lifecycle
```

A small **canvas SDK** (`pi_led_core/canvas.py`) gives plugins pixel fonts (a 5×7 pixel
font + a 3×5 micro font), color helpers (HSV, pulses, rainbows, sparkle), and shape/scroll
utilities tuned for a 64×64 grid.

---

## The apps we built

- **World Cup** (`apps/worldcup/`) — live from ESPN's public scoreboard (no key). Today's
  and upcoming matches, live/HT/FT states with a goal-flash, **all scorers** (pulled from
  the per-event summary, since the scoreboard feed is only partial) and **penalty-shootout
  winners**, group standings, and a **knockout bracket** rendered as a converging tree with
  hand-drawn pixel **flags** + team codes. Which knockout rounds show is configurable, so
  the bracket can track the tournament as it advances.
- **Weather** (`apps/weather/`) — [Open-Meteo](https://open-meteo.com) (free, no key):
  current conditions with hand-drawn pixel-art icons + a short daily forecast. Set the city
  in config.
- **Clock** (`apps/clock/`) — a dual-timezone digital face (two zones with dates + seconds)
  and an analog face. Also the reference "copy me to start a new app" plugin.
- **Messages** (`apps/messages/`) — a static message set from the web UI, with selectable
  animations (solid / rainbow / spectrum / breathe / wave / scroll / sparkle).
- **Ambient** (`apps/ambient/`) — always-on eye-candy: plasma, fire, "matrix" rain,
  starfield, Conway's Game of Life. Heavy effects compute at reduced resolution and scale
  up to stay within a Pi 3B's budget.
- **Carousel** (`apps/carousel/`) — the orchestrator: rotates the panel through a
  configured list of views. Some views (e.g. the day's matches) get a dwell long enough to
  page through all their content before the carousel moves on.

---

## Running it

**On a laptop (no hardware needed)** — everything renders to a preview PNG:

```bash
pip install -e .
python -m controller.runner        # renderer → writes a preview PNG each frame
python -m controller.web           # web app: live preview + admin at :5070
```

Open the web app to see the live preview and switch views. On the Pi with the panel
connected, the identical command drives the real display.

---

## Writing your own app (plugin)

The extension model is one folder + one line:

```bash
cp -r apps/clock apps/myapp        # clock is the minimal reference plugin
# edit apps/myapp/plugin.py: rename the class + `id`, implement render()
```

```python
# apps/__init__.py
from .myapp import MyApp
ALL_APPS = [ ..., MyApp() ]        # register it — its views appear automatically
```

That's it — the view shows up in the admin switcher and can be added to the carousel.
Keep data/config/lifecycle in `plugin.py` and pixel layout in a `render.py`/`pages/`
module; use the `canvas` SDK for drawing.

---

## Repo layout

```
pi_led_core/     rendering engine — LedApp contract, registry, state, sinks, canvas SDK
apps/            the plugins (worldcup, weather, clock, messages, ambient, carousel)
controller/      the two processes: runner (renderer) + web (admin/preview) + config
deploy/          systemd units, reverse-proxy snippet, hardware & deploy notes
```

---

Built with [Claude Code](https://claude.com/claude-code).
