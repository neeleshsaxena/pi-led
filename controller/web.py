from __future__ import annotations

import io
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from apps import ALL_APPS
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
def admin(request: Request, _: str = Depends(admin_required)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "catalog": registry.catalog(),
            "active": state.active,
            "message_cfg": state.config_for("messages"),
            "colors": list(COLORS.keys()),
            "viz_choices": list(VIZ_CHOICES),
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
