"""Reminders — a little to-do list on the panel.

Shows your active (not-done) reminders as a scrolling ticker; each can carry an
optional due date (overdue reads red). Manage them from a self-contained admin
page at /admin/apps/reminders/ — add (text + optional date), mark done, delete.

Data/config/lifecycle live here (lead-owned); pixel layout lives in render.py
(UI-owned). Reminders are stored in the `reminders` config as {"items": [ {id,
text, date, done}, ... ]}.
"""
from __future__ import annotations

import html
import os
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .render import render_reminders

TZ = ZoneInfo(os.environ.get("REMINDERS_TZ", "America/Los_Angeles"))


def _today() -> date:
    return datetime.now(TZ).date()


class ReminderApp(LedApp):
    id = "reminders"
    name = "Reminders"

    def default_config(self) -> dict:
        return {"items": []}  # each: {id, text, date (ISO or ""), done}

    def _active(self, cfg: dict) -> list[tuple[str, int | None, str]]:
        """Active reminders as (text, days_until|None, date_label), soonest first."""
        out: list[tuple[str, int | None, str]] = []
        for it in cfg.get("items") or []:
            if it.get("done"):
                continue
            text = str(it.get("text", "")).strip()
            if not text:
                continue
            days: int | None = None
            label = ""
            raw = str(it.get("date") or "").strip()
            if raw:
                try:
                    d = date.fromisoformat(raw)
                    days = (d - _today()).days
                    label = f"{d.strftime('%b').upper()} {d.day}"
                except ValueError:
                    pass
            out.append((text, days, label))
        out.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0))
        return out

    async def render(self, ctx: RenderContext) -> Image.Image:
        return render_reminders(self._active(ctx.config or {}), ctx.tick)

    def has_content(self, view_id: str, config: dict) -> bool:
        # Skip the carousel slot entirely when there are no open reminders.
        return bool(self._active(config or {}))

    def admin_router(self):
        from fastapi import APIRouter, Form
        from fastapi.responses import HTMLResponse, RedirectResponse

        from pi_led_core.state import ControllerState

        router = APIRouter()

        def _items() -> list[dict]:
            return list(ControllerState().config_for("reminders").get("items") or [])

        def _save(items: list[dict]) -> None:
            ControllerState().set_config("reminders", {"items": items})

        @router.get("/", response_class=HTMLResponse)
        def page() -> HTMLResponse:
            rows = ""
            for it in _items():
                tid = html.escape(str(it.get("id", "")))
                txt = html.escape(str(it.get("text", "")))
                raw = str(it.get("date") or "")
                datehtml = f'<span class=date>{html.escape(raw)}</span>' if raw else ""
                cls = "done" if it.get("done") else ""
                mark = "↺" if it.get("done") else "✓"
                rows += (
                    f'<li class="{cls}"><span class=txt>{txt}</span>{datehtml}'
                    f'<form method=post action="/admin/apps/reminders/toggle">'
                    f'<input type=hidden name=id value="{tid}"><button class=chk title="done">{mark}</button></form>'
                    f'<form method=post action="/admin/apps/reminders/delete">'
                    f'<input type=hidden name=id value="{tid}"><button class=del title="delete">✕</button></form></li>'
                )
            return HTMLResponse(_PAGE.format(rows=rows or '<li class=empty>No reminders yet.</li>'))

        @router.post("/add")
        def add(text: str = Form(...), due: str = Form("")) -> RedirectResponse:
            text = text.strip()
            if text:
                items = _items()
                items.append(
                    {"id": str(int(time.time() * 1000)), "text": text[:80], "date": due.strip(), "done": False}
                )
                _save(items)
            return RedirectResponse("/admin/apps/reminders/", status_code=303)

        @router.post("/toggle")
        def toggle(id: str = Form(...)) -> RedirectResponse:
            items = _items()
            for it in items:
                if str(it.get("id")) == id:
                    it["done"] = not it.get("done")
            _save(items)
            return RedirectResponse("/admin/apps/reminders/", status_code=303)

        @router.post("/delete")
        def delete(id: str = Form(...)) -> RedirectResponse:
            _save([it for it in _items() if str(it.get("id")) != id])
            return RedirectResponse("/admin/apps/reminders/", status_code=303)

        return router


_PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>pi-led · reminders</title>
<style>
 :root{{--bg:#0c0d11;--card:#15171e;--border:#272b36;--text:#eceef3;--muted:#8b93a7;--accent:#ff7a18;--green:#22c55e;--red:#ef4444}}
 *{{box-sizing:border-box}} body{{margin:0 auto;max-width:460px;background:radial-gradient(120% 80% at 50% -10%,#15171f,#0c0d11 60%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;padding:20px 14px 48px}}
 h1{{font-size:1.15rem;letter-spacing:.5px;margin:0 0 16px}}
 form.add{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}}
 input[type=text],input[type=date]{{padding:12px;background:#0c0d11;border:1px solid var(--border);border-radius:11px;color:var(--text);font:inherit}}
 input[type=text]{{flex:1;min-width:150px}} input[type=text]:focus,input[type=date]:focus{{outline:none;border-color:var(--accent)}}
 .add button{{padding:12px 18px;border:none;border-radius:11px;background:linear-gradient(180deg,#ffa04d,var(--accent));color:#1a0c00;font-weight:700}}
 ul{{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px}}
 li{{display:flex;align-items:center;gap:8px;background:linear-gradient(180deg,#1b1e27,var(--card));border:1px solid var(--border);border-radius:12px;padding:11px 12px}}
 li.done .txt{{text-decoration:line-through;color:var(--muted)}}
 li .txt{{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}}
 li .date{{color:var(--accent);font-size:.78rem;font-variant-numeric:tabular-nums;white-space:nowrap}}
 li form{{margin:0}} li button{{width:36px;height:36px;border-radius:9px;border:1px solid var(--border);background:#1b1e27;color:var(--text);font-size:1.05rem;cursor:pointer}}
 li .chk{{border-color:var(--green);color:var(--green)}} li .del{{border-color:var(--red);color:var(--red)}}
 li.empty{{justify-content:center;color:var(--muted)}}
 a{{color:#3b82f6;text-decoration:none;font-size:.9rem;display:inline-block;margin-top:18px}}
</style></head><body>
<h1>\U0001f4dd Reminders</h1>
<form class=add method=post action="/admin/apps/reminders/add">
 <input type=text name=text placeholder="New reminder…" maxlength=80 autocomplete=off required>
 <input type=date name=due title="optional due date">
 <button type=submit>Add</button>
</form>
<ul>{rows}</ul>
<a href="/admin">← back to control</a>
</body></html>"""
