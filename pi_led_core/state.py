from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

# Default lives at the repo root (parent of this package).
STATE_FILE = Path(os.environ.get("PI_LED_STATE", str(Path(__file__).resolve().parent.parent / ".state.json")))


class ControllerState:
    """Cross-process controller state, JSON-backed and mtime-synced.

    Shape:
        {"active": "<plugin>:<view>", "configs": {"<plugin id>": {<config>}, ...}}

    `active` is a fully-qualified view key (e.g. "worldcup:today"). `configs`
    holds per-plugin config keyed by plugin id (e.g. the message text).

    The web process writes (admin switches the active view / edits a config);
    the renderer process reads. Reads pick up out-of-process writes by checking
    the file's mtime on each access — same pattern as match-day-live.
    """

    def __init__(self, default_active: str = "", defaults: dict | None = None, path: Path = STATE_FILE):
        self._lock = Lock()
        self._path = Path(path)
        self._active = default_active
        self._configs: dict[str, dict] = {k: dict(v) for k, v in (defaults or {}).items()}
        self._mtime = 0.0
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._active = data.get("active", self._active)
            for plugin_id, cfg in (data.get("configs") or {}).items():
                base = dict(self._configs.get(plugin_id, {}))
                base.update(cfg or {})
                self._configs[plugin_id] = base
            self._mtime = self._path.stat().st_mtime
        except Exception:
            pass

    def _refresh_if_changed(self) -> None:
        try:
            mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
        except OSError:
            return
        if mtime != self._mtime:
            self._load()

    def _save(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps({"active": self._active, "configs": self._configs}, indent=2))
        os.replace(tmp, self._path)
        try:
            self._mtime = self._path.stat().st_mtime
        except OSError:
            pass

    @property
    def active(self) -> str:
        with self._lock:
            self._refresh_if_changed()
            return self._active

    def set_active(self, view_key: str) -> str:
        with self._lock:
            self._refresh_if_changed()
            self._active = view_key
            self._save()
            return self._active

    def config_for(self, plugin_id: str) -> dict:
        with self._lock:
            self._refresh_if_changed()
            return dict(self._configs.get(plugin_id, {}))

    def set_config(self, plugin_id: str, cfg: dict) -> dict:
        with self._lock:
            self._refresh_if_changed()
            base = dict(self._configs.get(plugin_id, {}))
            base.update(cfg)
            self._configs[plugin_id] = base
            self._save()
            return base

    def snapshot(self) -> dict:
        with self._lock:
            self._refresh_if_changed()
            return {"active": self._active, "configs": {k: dict(v) for k, v in self._configs.items()}}
