from __future__ import annotations

from .plugin import LedApp, make_view_key, parse_view_key


class AppRegistry:
    """Holds the set of LED plugins keyed by id. Core stays independent of the
    concrete plugins — the controller builds this from `apps.ALL_APPS`."""

    def __init__(self, apps: list[LedApp]):
        self._apps: dict[str, LedApp] = {}
        for app in apps:
            if not app.id:
                raise ValueError(f"plugin {app!r} has no id")
            if app.id in self._apps:
                raise ValueError(f"duplicate plugin id: {app.id!r}")
            self._apps[app.id] = app

    def get(self, app_id: str) -> LedApp | None:
        return self._apps.get(app_id)

    def all(self) -> list[LedApp]:
        return list(self._apps.values())

    def ids(self) -> list[str]:
        return list(self._apps.keys())

    def catalog(self) -> list[dict]:
        """Flat list of every selectable view across all plugins, for the admin UI.
        Each entry: {key, plugin_id, view_id, label}."""
        out: list[dict] = []
        for app in self._apps.values():
            for view in app.views():
                out.append(
                    {
                        "key": make_view_key(app.id, view.id),
                        "plugin_id": app.id,
                        "view_id": view.id,
                        "label": view.label,
                    }
                )
        return out

    def resolve(self, view_key: str) -> tuple[LedApp | None, str]:
        """'worldcup:today' -> (worldcup app, 'today'). Unknown plugin -> (None, view_id)."""
        plugin_id, view_id = parse_view_key(view_key)
        return self._apps.get(plugin_id), view_id

    async def start_all(self) -> None:
        for app in self._apps.values():
            await app.start()

    async def close_all(self) -> None:
        for app in self._apps.values():
            try:
                await app.aclose()
            except Exception as e:  # noqa: BLE001 - shutdown best-effort
                print(f"[registry] {app.id} aclose error: {type(e).__name__}: {e}")
