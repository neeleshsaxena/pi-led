# uvmon — Pi under-voltage / throttle monitor

A tiny systemd timer that samples `vcgencmd get_throttled` once a minute and logs
to the journal **only on state changes** (tag `uvmon`). It's the proactive half of
diagnosing the panel's brownouts: it catches voltage *sags* — even ones that don't
crash the box — instead of waiting for a full hard reset.

Pairs with **persistent journald** (`Storage=persistent` in
`/etc/systemd/journald.conf`) so the record survives the reboot after a brownout.

## Read the data

```bash
journalctl -t uvmon                 # full voltage timeline (state changes only)
journalctl -t uvmon -p warning      # just under-voltage / throttle events
vcgencmd get_throttled              # instantaneous flags (0x0 = clean)
```

Flag bits: `0x1` under-voltage now · `0x4` throttled now · `0x8` soft-temp now ·
`0x10000` under-voltage *occurred* · `0x40000` throttling *occurred* (latched until
reboot). A reading like `0x50005` = under-voltage now **and** since boot → power problem.

## Install (one time, on the Pi)

The script is kept in the synced repo (`deploy/push.sh` updates it); only the units
are installed to the system. From the repo on the Pi:

```bash
chmod +x deploy/uvmon/uvmon.sh
sudo cp deploy/uvmon/uvmon.service deploy/uvmon/uvmon.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now uvmon.timer
sudo systemctl start uvmon.service     # log an immediate baseline
```

`uvmon.service` runs `deploy/uvmon/uvmon.sh` by absolute path — if your `PI_DEST`
isn't `/home/pi/pi-led/`, edit the `ExecStart=` line to match.

## Remove

```bash
sudo systemctl disable --now uvmon.timer
sudo rm /etc/systemd/system/uvmon.service /etc/systemd/system/uvmon.timer
sudo systemctl daemon-reload
```
