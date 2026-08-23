from __future__ import annotations

import io
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from apps import ALL_APPS
from apps.epl.espn import EplClient
from apps.messages.plugin import COLORS
from apps.messages.render import VIZ_CHOICES
from pi_led_core.canvas import new_canvas
from pi_led_core.matrix import PREVIEW_PATH, PREVIEW_SCALE
from pi_led_core.registry import AppRegistry
from pi_led_core.state import ControllerState

from .auth import admin_required
from .config import DEFAULT_ACTIVE

registry = AppRegistry(ALL_APPS)
_defaults = {a.id: a.default_config() for a in registry.all()}
state = ControllerState(default_active=DEFAULT_ACTIVE, defaults=_defaults)

app = FastAPI(title="pi-led controller")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# Offline fallback for the EPL favorite-team dropdown: used only if the keyless
# ESPN standings call fails/returns empty, so the admin page never crashes. The
# live standings() call supplies the authoritative names + abbreviations.
_EPL_FALLBACK_TEAMS = [
    {"abbr": "ARS", "name": "Arsenal"},
    {"abbr": "AVL", "name": "Aston Villa"},
    {"abbr": "BOU", "name": "Bournemouth"},
    {"abbr": "BRE", "name": "Brentford"},
    {"abbr": "BHA", "name": "Brighton"},
    {"abbr": "CHE", "name": "Chelsea"},
    {"abbr": "CRY", "name": "Crystal Palace"},
    {"abbr": "EVE", "name": "Everton"},
    {"abbr": "FUL", "name": "Fulham"},
    {"abbr": "LIV", "name": "Liverpool"},
    {"abbr": "MNC", "name": "Man City"},
    {"abbr": "MNU", "name": "Man United"},
    {"abbr": "NEW", "name": "Newcastle"},
    {"abbr": "NFO", "name": "Nottingham Forest"},
    {"abbr": "TOT", "name": "Tottenham"},
    {"abbr": "WHU", "name": "West Ham"},
    {"abbr": "WOL", "name": "Wolves"},
]


async def _epl_teams(favorite: str = "") -> list[dict]:
    """[{abbr, name}, …] for the favorite-team dropdown, alpha by name.

    Pulls the live table from the keyless ESPN client; on any failure falls back to
    a static list so the admin page still renders. Guarantees the current favorite
    is present (so its <option> can be pre-selected even if the API omits it)."""
    client = EplClient()
    try:
        rows = await client.standings()
    except Exception:  # noqa: BLE001 - the admin page must never crash on a bad fetch
        rows = []
    finally:
        await client.close()

    teams = [{"abbr": r["abbr"], "name": r["name"]} for r in rows if r.get("abbr")]
    if not teams:
        teams = list(_EPL_FALLBACK_TEAMS)
    teams.sort(key=lambda t: t["name"])

    fav = (favorite or "").upper()
    if fav and fav not in {t["abbr"] for t in teams}:
        teams.insert(0, {"abbr": fav, "name": fav})
    return teams

# Mount any per-plugin admin routes under /admin/apps/<id>.
for _app in registry.all():
    router = _app.admin_router()
    if router is not None:
        app.include_router(router, prefix=f"/admin/apps/{_app.id}", dependencies=[Depends(admin_required)])


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/preview")


@app.get("/preview", response_class=HTMLResponse)
def preview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "preview.html",
        {"scale": PREVIEW_SCALE},
    )


@app.get("/led-preview.png")
def led_preview_png() -> Response:
    """Serve the current dev-sink frame; a blank panel if none rendered yet."""
    if PREVIEW_PATH.exists():
        return Response(PREVIEW_PATH.read_bytes(), media_type="image/png")
    buf = io.BytesIO()
    new_canvas().save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/api/state")
def api_state() -> dict:
    return {"active": state.active, "catalog": registry.catalog()}


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, _: str = Depends(admin_required)) -> HTMLResponse:
    epl_cfg = state.config_for("epl")
    epl_teams = await _epl_teams(str(epl_cfg.get("favorite", "")))
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "catalog": registry.catalog(),
            "active": state.active,
            "message_cfg": state.config_for("messages"),
            "colors": list(COLORS.keys()),
            "viz_choices": list(VIZ_CHOICES),
            "epl_cfg": epl_cfg,
            "epl_teams": epl_teams,
            "scale": PREVIEW_SCALE,
        },
    )


@app.post("/admin/view")
def set_view(view: str = Form(...), _: str = Depends(admin_required)) -> RedirectResponse:
    state.set_active(view)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/messages")
def set_message(
    text: str = Form(""),
    color: str = Form("white"),
    viz: str = Form("solid"),
    activate: str = Form(""),
    _: str = Depends(admin_required),
) -> RedirectResponse:
    state.set_config("messages", {"text": text, "color": color, "viz": viz})
    if activate:
        state.set_active("messages:main")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/epl")
def set_epl(favorite: str = Form(""), _: str = Depends(admin_required)) -> RedirectResponse:
    # Only the favorite is editable from the UI; league stays whatever the stored
    # config holds (default eng.1). Empty value = no favorite ("— none —").
    state.set_config("epl", {"favorite": favorite.strip().upper()})
    return RedirectResponse("/admin", status_code=303)
