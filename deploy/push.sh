#!/usr/bin/env bash
# Push local pi-led code to the Pi and restart the services so changes show on
# the real LED panel. The Pi uses an editable install (pip install -e .), so a
# restart is all that's needed to pick up code/template changes — no reinstall.
#
# Usage:
#   deploy/push.sh                  # sync + restart both services (keep current view)
#   deploy/push.sh worldcup:today   # ...then switch the panel to that view
#   deploy/push.sh messages:main    # views: messages:main | worldcup:{today,next,standings}
#
# Re-run `pip install -e .` on the Pi only if you changed dependencies in
# pyproject.toml (rare). For normal code/UI iteration, this script is all you need.
set -euo pipefail

PI="${PI_HOST:-pi@raspberrypi.local}"
DEST="${PI_DEST:-/home/pi/pi-led/}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/"

echo "→ syncing  $SRC"
echo "      ->   $PI:$DEST"
# Excluded paths are also protected from --delete, so the Pi's .state.json and
# .admin_password are never touched.
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '.state.json' --exclude '.admin_password' \
  --exclude '.git' --exclude '*.egg-info' \
  "$SRC" "$PI:$DEST"

echo "→ restarting renderer + web"
ssh "$PI" 'sudo systemctl restart pi-led-renderer pi-led-web'

echo "→ waiting for web app to come up"
ssh "$PI" 'for i in $(seq 1 20); do c=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5070/preview); [ "$c" != "000" ] && { echo "   web ready (HTTP $c)"; break; }; sleep 1; done'

if [ "${1:-}" != "" ]; then
  echo "→ switching active view to '$1'"
  ssh "$PI" "code=\$(curl -s -o /dev/null -w '%{http_code}' -u admin:\$(cat $DEST.admin_password) -d 'view=$1' http://127.0.0.1:5070/admin/view); echo \"   admin/view -> HTTP \$code\""
fi

echo "→ checking renderer health"
ssh "$PI" 'printf "   renderer: %s\n" "$(systemctl is-active pi-led-renderer)"; sudo journalctl -u pi-led-renderer -n 5 --no-pager | grep -E "\[led\]" | tail -2; if sudo journalctl -u pi-led-renderer -n 40 --no-pager | grep -qiE "frame error|Traceback"; then echo "   ⚠ frame errors in log — check: ssh '"$PI"' sudo journalctl -u pi-led-renderer -n 40"; fi'

echo "✓ pushed — watch the panel."
