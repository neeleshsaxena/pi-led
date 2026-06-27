# pi-led — physical hardware setup (driver guide)

**For the setup agent.** This is a self-contained, step-by-step guide to
physically assemble and power-on the LED panel, then confirm "first light" with
a built-in test pattern. Walk the user through it **one step at a time**, wait
for confirmation between steps, and **do not skip the power-off / polarity
checks** — reversed panel power can damage the panel.

You are driving *only the physical setup + first-light test*. The pi-led
software deploy (systemd, Caddy, app verification) is owned by a different agent
and is **out of scope here** — stop after the hzeller demo test passes.

---

## Context (already done — don't redo)

- **Pi:** Raspberry Pi 3 Model B, reachable at `ssh pi@raspberrypi.local`
  (passwordless ed25519 key auth from the user's Mac; `sudo` is passwordless).
  Also answers at `ledpanel.local`.
- **hzeller `rpi-rgb-led-matrix` library is already built** on the Pi at
  `~/rpi-rgb-led-matrix/`. The C++ demo binary exists at
  `~/rpi-rgb-led-matrix/examples-api-use/demo`. You do **not** need to build it.
- **There is a live web app on this Pi** (`match-day-live.service`, the World
  Cup scoreboard on port 5050). The reboot in Step 8 will briefly bounce it; it
  auto-restarts. Mention this to the user before rebooting.

## The hardware in hand

| Item | Detail |
|---|---|
| Panel | Adafruit #4732 — single **64×64 HUB75, P3** pitch |
| Driver board | Adafruit RGB Matrix Bonnet **#3211** |
| PSU | 5V 4A barrel-plug supply (Adafruit #1466) |
| Data cable | 16-pin (2×8) IDC ribbon (came with the panel) |
| Power cable | Red/black panel power harness (came with the panel) |
| Pi power | Pi's **own** USB/USB-C supply (separate from the panel PSU) |

**Soldering — read carefully, there are TWO different jumpers:**

1. **E-address line jumper — REQUIRED for 64×64 panels.** On the Bonnet's
   underside, solder the center **`E`** pad to the **`8`** pad (leave `16`
   clear). The Bonnet leaves the 5th address line (E) disconnected by default;
   without this bridge only ~half a 64-row panel is addressable and **no
   software flag can fix it** (multiplexing, row-addr-type, scan depth, etc. all
   have zero effect because the signal never physically reaches the panel). This
   is Adafruit's documented procedure for their 64×64 panels including #4732.
   **Confirmed required during bring-up 2026-06-26.** Walk the user through this
   bridge and confirm it's done before expecting a full-panel image.

2. **GPIO4↔GPIO18 PWM jumper — optional, leave unsoldered.** This one only
   improves refresh smoothness and lets you use `adafruit-hat-pwm`. We do NOT
   solder it, so we use the `adafruit-hat` GPIO mapping. Don't conflate it with
   the E jumper above — they are different pads for different purposes.

---

## ⚠️ Safety rules (state these to the user up front)

1. **All power disconnected** during assembly — Pi USB unplugged AND panel PSU
   unplugged — until Step 7.
2. **Panel power polarity is the one thing that can fry the panel:**
   **RED → `+`, BLACK → `−`** on the bonnet screw terminal. Double-check before
   any power.
3. Power the **panel** (via the bonnet) and the **Pi** from **separate**
   supplies. Don't try to run the Pi off the matrix PSU.

---

## Assembly steps

Walk through these in order. Confirm each before moving on.

### Step 1 — Power everything off
- Unplug the Pi's USB power.
- Make sure the panel PSU (barrel plug) is unplugged from the wall and from the
  bonnet.

### Step 2 — Seat the Bonnet on the Pi
- Press the Bonnet #3211 straight down onto the Pi's 40-pin GPIO header until all
  pins are fully seated. It covers the top of the Pi. No wires yet.

### Step 3 — Panel power harness → panel
- Plug the red/black power harness's 4-pin connector into the **panel's power
  input**. The two RED wires are +5V, the two BLACK are ground.

### Step 4 — Panel power harness → Bonnet screw terminal ⚠️ polarity-critical
- The other end of the harness has spade lugs. On the bonnet's green screw
  terminal block:
  - **RED lug → `+` terminal**
  - **BLACK lug → `−` terminal**
- Loosen the screws, insert the lugs, tighten firmly so nothing can pull out.
- **Have the user read the terminal back to you: "red is in plus, black is in
  minus."** This is the critical check.

### Step 5 — Data ribbon → panel INPUT side
- Plug one end of the 16-pin IDC ribbon into the bonnet's IDC socket.
- Plug the other end into the panel's **INPUT** connector.
  - HUB75 panels have **arrows printed on the back** pointing from INPUT →
    OUTPUT. Connect to the connector the arrows point **away from** (the start).
  - If you pick the wrong (OUTPUT) side it won't damage anything — the panel
    just stays dark — so this is recoverable.

### Step 6 — Final pre-power check (read each aloud)
- [ ] Bonnet fully seated on the 40-pin header.
- [ ] Data ribbon connected, on the panel's **INPUT** side.
- [ ] Panel power: **RED → `+`, BLACK → `−`** — confirmed.
- [ ] Both power supplies still unplugged.

### Step 7 — Power on
1. Plug the **5V 4A PSU barrel plug into the bonnet's barrel jack** (powers the
   panel). The panel may show faint random pixels — normal until software drives
   it.
2. Plug in the **Pi's own USB power** separately. Wait ~30s for it to boot and
   rejoin the network (`ping raspberrypi.local` until it responds).

---

## Software: disable onboard sound (one-time), then first-light test

### Step 8 — Disable onboard sound + reboot
The panel's timing conflicts with the Pi's onboard audio peripheral
(`snd_bcm2835`), causing flicker. Disable it once.

**Tell the user this reboots the Pi and briefly interrupts the match-day-live
web app (it auto-restarts).** Then run, over SSH:

```bash
# Turn audio off in the boot config (Trixie path)
sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' /boot/firmware/config.txt
# Belt-and-suspenders: also blacklist the module
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
sudo reboot
```

Wait for the Pi to come back (`ping raspberrypi.local`, then SSH in again).
Confirm it took:

```bash
grep audio /boot/firmware/config.txt   # should show dtparam=audio=off
lsmod | grep snd_bcm2835               # should print nothing
```

### Step 9 — First-light test (hzeller built-in demo)
This runs hzeller's own C++ demo — **no pi-led code involved** — purely to prove
the wiring is correct. `D0` is a rotating square. Must run as root (`sudo`).

```bash
sudo ~/rpi-rgb-led-matrix/examples-api-use/demo -D0 \
  --led-gpio-mapping=adafruit-hat \
  --led-rows=64 --led-cols=64 --led-chain=1 \
  --led-slowdown-gpio=2
```

**Expected:** a smooth rotating square fills the 64×64 panel. Let it run a few
seconds, then `Ctrl-C` to stop.

**Reading the result / troubleshooting:**
| Symptom | Likely cause / fix |
|---|---|
| Smooth rotating square | ✅ Success. Setup is done — hand back to the lead agent. |
| Panel totally dark | Data ribbon on the **OUTPUT** side (Step 5) — swap to INPUT. Or PSU not plugged into the bonnet. |
| Image garbled / tearing / wrong colors | Bump `--led-slowdown-gpio` to `3` then `4` and rerun. (Pi 3B sometimes needs a higher value.) |
| Only top or bottom half lit, or doubled | **Almost certainly the missing E→8 solder bridge** (see the soldering section above) — this is a *hardware* fix, not a flag. Do that bridge first. Only if it persists after bridging is it a multiplex/row-addr issue to report back. |
| Flickering | Confirm Step 8 (audio off) actually took. |
| Colors swapped (e.g. red↔blue) | Note it — lead agent sets `--led-rgb-sequence`. |

Once the rotating square looks right, **stop here.** Report the working
`--led-slowdown-gpio` value (and any other flag you had to change) back to the
lead agent — those values get baked into the pi-led renderer config.

---

## Handback

When the demo passes, tell the lead agent:
1. ✅ First light confirmed.
2. The `--led-slowdown-gpio` value that worked.
3. Any flags you had to change from the defaults above (multiplexing, rgb
   sequence, etc.).

The lead agent then deploys the pi-led renderer (which uses these same values
via `LED_GPIO_SLOWDOWN` and the `adafruit-hat` mapping) and verifies the
`messages` and `worldcup` apps on the panel.
