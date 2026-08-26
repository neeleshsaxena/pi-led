#!/usr/bin/env bash
# Shared, location-independent deploy wrapper — call it from ANY directory, most
# usefully from inside an app folder (apps/<name>/) while you're iterating on it.
#
# The Pi runs ONE editable install with a single renderer that owns the panel, so
# there is no per-app deploy — every push syncs the whole repo. This wrapper just
# removes the friction: it finds the repo root on its own (no cd-ing around),
# figures out which app you're working on, hands off to deploy/push.sh, and jumps
# the panel straight to that app's view so you see your change immediately.
#
# Usage (from anywhere — e.g. while editing apps/epl/render.py):
#   ../../deploy/app-deploy.sh           # detect app from the current dir; deploy;
#                                        #   pin that app's first view on the panel
#   deploy/app-deploy.sh epl             # deploy; pin the 'epl' app's first view
#   deploy/app-deploy.sh epl:table       # deploy; pin an explicit "<app>:<view>"
#   deploy/app-deploy.sh --no-view       # deploy; keep whatever view is showing
#   deploy/app-deploy.sh -n              # dry run: show what it would do, don't deploy
#
# Tip: add an alias so it's one word from inside any app dir:
#   alias pideploy="$(git -C . rev-parse --show-toplevel 2>/dev/null)/deploy/app-deploy.sh"
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

want_view=1
dry_run=0
target=""
for arg in "$@"; do
  case "$arg" in
    --no-view)     want_view=0 ;;
    -n|--dry-run)  dry_run=1 ;;
    -h|--help)     sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*)            echo "unknown option: $arg" >&2; exit 2 ;;
    *)             target="$arg" ;;
  esac
done

# Resolve the app id + view to pin.
#   explicit "<app>:<view>"  -> use as-is
#   explicit "<app>"         -> resolve its first view below
#   nothing                  -> detect "<app>" from the current path (apps/<name>/…)
app_id=""
view_key=""
if [[ "$target" == *:* ]]; then
  view_key="$target"
  app_id="${target%%:*}"
elif [[ -n "$target" ]]; then
  app_id="$target"
else
  cwd="$(pwd)"
  case "$cwd" in
    "$ROOT"/apps/*)
      rel="${cwd#"$ROOT"/apps/}"
      app_id="${rel%%/*}"
      ;;
  esac
fi

# Turn an app id into its first view key ("<app>:<view>") via the local registry.
# Best-effort: needs the local venv; on any failure we just deploy without pinning.
if [[ $want_view -eq 1 && -z "$view_key" && -n "$app_id" ]]; then
  PY="$ROOT/.venv/bin/python"
  [ -x "$PY" ] || PY="python3"
  view_key="$(cd "$ROOT" && PYTHONPATH="$ROOT" "$PY" - "$app_id" <<'PYEOF' 2>/dev/null || true
import sys
try:
    from apps import ALL_APPS
    app = next((a for a in ALL_APPS if a.id == sys.argv[1]), None)
    if app is not None:
        print(f"{app.id}:{app.views()[0].id}")
except Exception:
    pass
PYEOF
)"
  if [[ -z "$view_key" ]]; then
    echo "ℹ couldn't resolve a view for app '$app_id' (unknown id?); deploying without pinning a view." >&2
  fi
fi

if [[ -n "$app_id" ]]; then
  echo "▶ app: $app_id${view_key:+  → view: $view_key}"
else
  echo "▶ no specific app detected — full deploy, keeping the current view."
fi

# Build the push.sh argument list (a view key, or nothing).
set --
if [[ $want_view -eq 1 && -n "$view_key" ]]; then
  set -- "$view_key"
fi

if [[ $dry_run -eq 1 ]]; then
  echo "— dry run — would run: deploy/push.sh ${*:-(no view)}"
  exit 0
fi

exec "$HERE/push.sh" "$@"
