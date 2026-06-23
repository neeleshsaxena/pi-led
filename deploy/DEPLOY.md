# Deploying pi-led to the Pi

Mirrors the match-day-live deploy pattern. Web app on port **5070**, served at
`http://panel.local/` via Caddy. Until the HUB75 panel + Bonnet arrive the
renderer runs in **PNGSink** mode (preview only) — exactly like match-day-live.

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
sudo systemctl enable --now avahi-alias@panel.local.service
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
`http://panel.local/admin`.

## When the panel arrives

- Install hzeller `rpi-rgb-led-matrix` so `rgbmatrix` imports; the sink
  auto-switches from PNG to the panel.
- Update `pi-led-renderer.service` for GPIO access (run as root or grant
  privileges) and set `LED_GPIO_SLOWDOWN` / `LED_BRIGHTNESS`.
