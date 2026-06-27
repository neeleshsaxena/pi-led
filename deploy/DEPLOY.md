# Deploying pi-led to the Pi

Mirrors the match-day-live deploy pattern. Web app on port **5070**, served at
`http://ledpanel.local/` via Caddy. With the HUB75 panel + Bonnet installed the
renderer drives the real panel via `HzellerSink` (runs as root for GPIO); on a
machine without the `rgbmatrix` lib it falls back to **PNGSink** preview.

## 1. Sync code (from Mac)

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' \
  --exclude '.state.json' --exclude '.admin_password' \
  --exclude '.git' \
  ~/workspace/pi-projects/pi-led/ \
  pi@ledpanel.local:/home/pi/pi-led/
```

## 2. One-time venv + install (on Pi)

```bash
ssh pi@ledpanel.local
cd /home/pi/pi-led
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 3. mDNS alias (on Pi)

```bash
sudo systemctl enable --now avahi-alias@ledpanel.service   # publishes ledpanel.local
```

## 4. Caddy route (on Pi)

Append `deploy/Caddyfile.snippet` to `/etc/caddy/Caddyfile`, then:

```bash
sudo systemctl reload caddy
```

## 5. systemd units (on Pi)

```bash
sudo cp deploy/pi-led-web.service /etc/systemd/system/
sudo cp deploy/pi-led-renderer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-led-web pi-led-renderer
```

Check: `systemctl status pi-led-web pi-led-renderer` and browse
`http://ledpanel.local/admin`.

## Iterate on the real panel (after first deploy)

Once the services exist on the Pi, the edit→see-it-on-the-panel loop is one
command. The Pi uses an **editable install**, so a service restart picks up code
and template changes — no reinstall needed.

```bash
# from the repo root on the Mac:
deploy/push.sh                  # sync code + restart renderer & web
deploy/push.sh worldcup:today   # ...and switch the panel to a view
# views: messages:main | worldcup:today | worldcup:next | worldcup:standings
```

`push.sh` rsyncs the repo to the Pi (protecting the Pi's `.state.json` /
`.admin_password`), restarts both services, waits for the web app, optionally
switches the active view, and prints renderer health (flags any frame errors).
A restart blanks the panel for ~2–3 s, then it resumes.

Only re-run `.venv/bin/pip install -e .` on the Pi if `pyproject.toml`
dependencies changed (rare). Override the target host with `PI_HOST=...`.

**Workflow with the UI/UX agent:** that agent iterates locally in PNG-preview
mode and never touches the Pi (see `UI-UX-WORKSTREAM.md`). When you want to see
their changes on real hardware, run `deploy/push.sh` — that's the bridge from
their local work to the panel.

## When the panel arrives

- Install hzeller `rpi-rgb-led-matrix` so `rgbmatrix` imports; the sink
  auto-switches from PNG to the panel.
- Update `pi-led-renderer.service` for GPIO access (run as root or grant
  privileges) and set `LED_GPIO_SLOWDOWN` / `LED_BRIGHTNESS`.
