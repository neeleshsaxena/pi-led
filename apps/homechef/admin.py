"""Home Chef admin UI — pantry, suggestions, dish library, weekly menu.

Split out from plugin.py (unlike the simpler one-concern apps) because this
plugin has four distinct admin surfaces instead of one config form. Plain
HTML forms + redirects throughout, same idiom as reminders.py/plants.py — no
fetch/JSON here. Because this module is only ever imported lazily, from
HomeChefApp.admin_router() (never at plugin.py's top level), importing
fastapi here at module scope is safe — it only loads in the web process.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from pi_led_core.state import ControllerState

from . import seed_data
from .matcher import suggest_dishes
from .plugin import DAYS, HomeChefApp, today_day

BASE = "/admin/apps/homechef"
DAY_ABBR = {
    "monday": "MO", "tuesday": "TU", "wednesday": "WE", "thursday": "TH",
    "friday": "FR", "saturday": "SA", "sunday": "SU",
}

_STYLE = """<style>
 :root{--bg:#0c0d11;--card:#15171e;--card2:#1b1e27;--border:#272b36;--text:#eceef3;--muted:#8b93a7;--accent:#ff7a18;--green:#22c55e;--red:#ef4444}
 *{box-sizing:border-box}
 body{margin:0 auto;max-width:480px;background:radial-gradient(120% 80% at 50% -10%,#15171f,#0c0d11 60%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;padding:20px 14px 48px}
 h1{font-size:1.15rem;letter-spacing:.5px;margin:0 0 4px}
 p.sub{color:var(--muted);font-size:.85rem;margin:0 0 18px}
 .navgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px}
 .navcard{display:flex;flex-direction:column;align-items:center;gap:6px;padding:20px 10px;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--border);border-radius:14px;color:var(--text);text-decoration:none;font-weight:600;font-size:.95rem;line-height:1.6}
 .navcard:active{transform:translateY(1px)}
 .grouplabel{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:16px 0 8px}
 .chiprow{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px}
 .chiprow input{position:absolute;opacity:0;pointer-events:none}
 .chip{display:inline-flex;align-items:center;padding:9px 14px;border-radius:999px;background:#0c0d11;border:1px solid var(--border);color:var(--text);font-size:.85rem;cursor:pointer}
 input:checked+.chip{background:var(--green);border-color:var(--green);color:#06230f;font-weight:600}
 .chip.staple{opacity:.7}
 .cta{width:100%;min-height:52px;border:none;border-radius:12px;cursor:pointer;font:inherit;font-weight:700;font-size:1rem;color:#1a0c00;margin-top:16px;background:linear-gradient(180deg,#ffa04d,var(--accent))}
 .cta:active{transform:translateY(1px)}
 input[type=text]{width:100%;padding:12px 14px;background:#0c0d11;border:1px solid var(--border);border-radius:11px;color:var(--text);font:inherit;margin-bottom:10px}
 input[type=text]:focus,select:focus{outline:none;border-color:var(--accent)}
 select{width:100%;padding:12px 14px;background:#0c0d11;border:1px solid var(--border);border-radius:11px;color:var(--text);font:inherit;margin-bottom:10px}
 .dish{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--border);border-radius:14px;padding:14px;margin-bottom:10px}
 .dishhead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
 .badge{font-size:.68rem;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}
 .badge.ready{background:rgba(34,197,94,.18);color:var(--green)}
 .badge.missing{background:rgba(255,122,24,.16);color:var(--accent)}
 .pills{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
 .pill{font-size:.72rem;padding:3px 9px;border-radius:999px;background:#0c0d11;color:var(--muted);border:1px solid var(--border)}
 .pill.have{color:var(--green);border-color:var(--green)}
 .pill.miss{color:var(--accent);border-color:var(--accent)}
 .daytoggles{display:flex;gap:6px;flex-wrap:wrap}
 .daytoggles form{margin:0}
 .daybtn{min-width:34px;height:34px;padding:0 6px;border-radius:9px;border:1px solid var(--border);background:#0c0d11;color:var(--muted);font-weight:700;font-size:.72rem;cursor:pointer}
 .daybtn.on{background:var(--green);border-color:var(--green);color:#06230f}
 .delform{margin:0}
 .delbtn{width:32px;height:32px;border-radius:9px;border:1px solid var(--red);color:var(--red);background:#0c0d11;cursor:pointer}
 .menurow{display:flex;align-items:center;justify-content:space-between;gap:10px;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--border);border-radius:12px;padding:13px 16px;margin-bottom:8px;text-decoration:none;color:var(--text)}
 .menurow:active{transform:translateY(1px)}
 .menurow .d{font-weight:700;white-space:nowrap}
 .menurow .s{color:var(--muted);font-size:.82rem;flex:1;margin-left:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right}
 .pillbtns{display:flex;flex-wrap:wrap;gap:8px}
 .pillbtns form{margin:0}
 .pillbtn{padding:10px 14px;border-radius:999px;border:1px solid var(--border);background:#0c0d11;color:var(--text);font-size:.88rem;cursor:pointer}
 .pillbtn.on{background:var(--green);border-color:var(--green);color:#06230f;font-weight:600}
 .hint{color:var(--muted);font-size:.85rem;text-align:center;margin:18px 0}
 a.back{color:#3b82f6;text-decoration:none;font-size:.9rem;display:inline-block;margin-top:20px}
 .filters{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
 .filters a{padding:6px 12px;border-radius:999px;border:1px solid var(--border);color:var(--muted);text-decoration:none;font-size:.82rem}
 .filters a.active{background:var(--accent);border-color:var(--accent);color:#1a0c00;font-weight:700}
</style>"""


def _page(title: str, body: str, back: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>pi-led · {html.escape(title)}</title>
{_STYLE}</head><body>
<h1>{html.escape(title)}</h1>
{body}
<a class=back href="{back}">← back</a>
</body></html>"""
    )


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()


def _state() -> ControllerState:
    # home-chef's defaults aren't trivially empty like reminders'/plants' are,
    # so they're supplied on every read/write to self-heal a fresh install
    # that hasn't saved anything to .state.json yet.
    return ControllerState(defaults={"homechef": HomeChefApp().default_config()})


def _config() -> dict:
    return _state().config_for("homechef")


def _set(patch: dict) -> None:
    _state().set_config("homechef", patch)


def _ingredient_chip_groups(ingredients: list[dict], checked: set[str], field: str, idprefix: str) -> str:
    groups: dict[str, list[dict]] = {}
    for ing in ingredients:
        groups.setdefault(ing.get("category", "vegetable"), []).append(ing)

    out = []
    for cat_key in seed_data.CATEGORY_ORDER:
        items = groups.get(cat_key) or []
        if not items:
            continue
        out.append(f'<div class=grouplabel>{html.escape(seed_data.CATEGORY_LABELS[cat_key])}</div><div class=chiprow>')
        for ing in sorted(items, key=lambda i: i["name"]):
            name = ing["name"]
            cid = f"{idprefix}-{_slug(name)}"
            is_checked = "checked" if name in checked else ""
            staple_cls = " staple" if ing.get("is_staple") else ""
            out.append(
                f'<input type=checkbox id="{cid}" name="{field}" value="{html.escape(name)}" {is_checked}>'
                f'<label for="{cid}" class="chip{staple_cls}">{html.escape(name)}</label>'
            )
        out.append("</div>")
    return "".join(out)


def _toggle_menu(day: str, dish: str) -> None:
    if day not in DAYS or not dish:
        return
    cfg = _config()
    menu = {d: list(v or []) for d, v in (cfg.get("menu") or {}).items()}
    for d in DAYS:
        menu.setdefault(d, [])
    current = menu[day]
    if dish in current:
        current.remove(dish)
    else:
        current.append(dish)
    _set({"menu": menu})


def build_router() -> APIRouter:
    router = APIRouter()

    # ---------- index ----------

    @router.get("/", response_class=HTMLResponse)
    def index(restored: int = 0) -> HTMLResponse:
        cfg = _config()
        day = today_day()
        todays = (cfg.get("menu") or {}).get(day) or []
        summary = ", ".join(todays) if todays else "nothing planned yet"
        banner = '<p class=hint style="color:var(--green)">✓ Backup restored.</p>' if restored else ""
        body = f"""
        <p class=sub>What's for dinner, curated from what's in the kitchen.</p>
        {banner}
        <div class=navgrid>
          <a class=navcard href="pantry">\U0001f955<br>Pantry</a>
          <a class=navcard href="suggestions">\U0001f4a1<br>Suggestions</a>
          <a class=navcard href="dishes">\U0001f4d6<br>Dish Library</a>
          <a class=navcard href="menu">\U0001f4c5<br>Weekly Menu</a>
        </div>
        <p class=hint>TODAY ({html.escape(day.upper())}): {html.escape(summary)}</p>
        <div class=grouplabel style="margin-top:18px">Backup</div>
        <div class=navgrid>
          <a class=navcard href="export">\U0001f4be<br>Download backup</a>
          <a class=navcard href="restore">♻️<br>Restore</a>
        </div>
        """
        return _page("Home Chef", body, back="/admin")

    # ---------- pantry ----------

    @router.get("/pantry", response_class=HTMLResponse)
    def pantry_page() -> HTMLResponse:
        cfg = _config()
        checked = set(cfg.get("available") or [])
        chips = _ingredient_chip_groups(cfg.get("ingredients") or [], checked, field="available", idprefix="av")
        options = "".join(f'<option value="{k}">{html.escape(v)}</option>' for k, v in seed_data.CATEGORY_LABELS.items())
        body = f"""
        <p class=sub>Tap everything you've got right now, then save.</p>
        <form method=post action="{BASE}/pantry">
          {chips}
          <button type=submit class=cta>Save &amp; see suggestions →</button>
        </form>
        <div class=grouplabel style="margin-top:24px">Add an ingredient</div>
        <form method=post action="{BASE}/pantry/add">
          <input type=text name=name placeholder="e.g. Zucchini" maxlength=60 required>
          <select name=category>{options}</select>
          <button type=submit class=cta>Add</button>
        </form>
        """
        return _page("Pantry", body, back=f"{BASE}/")

    @router.post("/pantry")
    async def pantry_save(request: Request) -> RedirectResponse:
        form = await request.form()
        _set({"available": list(form.getlist("available"))})
        return RedirectResponse(f"{BASE}/suggestions", status_code=303)

    @router.post("/pantry/add")
    def pantry_add(name: str = Form(...), category: str = Form("vegetable")) -> RedirectResponse:
        name = name.strip()[:60]
        category = category if category in seed_data.CATEGORY_LABELS else "vegetable"
        if name:
            cfg = _config()
            ingredients = list(cfg.get("ingredients") or [])
            if not any(i["name"].lower() == name.lower() for i in ingredients):
                ingredients.append({"name": name, "category": category, "is_staple": False})
                _set({"ingredients": ingredients})
        return RedirectResponse(f"{BASE}/pantry", status_code=303)

    # ---------- suggestions ----------

    @router.get("/suggestions", response_class=HTMLResponse)
    def suggestions_page(max_missing: int = 2) -> HTMLResponse:
        cfg = _config()
        results = suggest_dishes(
            cfg.get("ingredients") or [], cfg.get("dishes") or [], cfg.get("available") or [], max_missing=max_missing
        )
        menu = cfg.get("menu") or {}

        filters = "".join(
            f'<a href="?max_missing={n}" class="{"active" if n == max_missing else ""}">{label}</a>'
            for n, label in ((0, "Ready only"), (1, "Missing ≤1"), (2, "Missing ≤2"), (4, "Missing ≤4"))
        )

        if not results:
            cards = '<p class=hint>No dishes match yet — mark more ingredients available, or loosen the filter above.</p>'
        else:
            parts = []
            for dish in results:
                name = dish["name"]
                missing = set(dish["missing"])
                pills = "".join(
                    f'<span class="pill {"miss" if ing in missing else "have"}">{html.escape(ing)}</span>'
                    for ing in dish["ingredients"]
                )
                badge = (
                    '<span class="badge ready">Ready to cook</span>'
                    if dish["is_full_match"]
                    else f'<span class="badge missing">Missing {dish["missing_count"]}</span>'
                )
                daybtns = "".join(
                    f"""<form method=post action="{BASE}/menu/toggle">
                      <input type=hidden name=dish value="{html.escape(name)}">
                      <input type=hidden name=day value="{d}">
                      <input type=hidden name=next value="suggestions?max_missing={max_missing}">
                      <button class="daybtn{' on' if name in (menu.get(d) or []) else ''}">{DAY_ABBR[d]}</button>
                    </form>"""
                    for d in DAYS
                )
                parts.append(
                    f'<div class=dish><div class=dishhead><b>{html.escape(name)}</b>{badge}</div>'
                    f'<div class=pills>{pills}</div><div class=daytoggles>{daybtns}</div></div>'
                )
            cards = "".join(parts)

        body = f"""
        <p class=sub>Curated from what's marked available. Click a day to add/remove.</p>
        <div class=filters>{filters}</div>
        {cards}
        """
        return _page("Suggestions", body, back=f"{BASE}/")

    # ---------- dish library ----------

    @router.get("/dishes", response_class=HTMLResponse)
    def dishes_page() -> HTMLResponse:
        cfg = _config()
        dishes = sorted(cfg.get("dishes") or [], key=lambda d: d["name"])
        if not dishes:
            rows = "<p class=hint>No dishes yet.</p>"
        else:
            parts = []
            for dish in dishes:
                pills = "".join(f"<span class=pill>{html.escape(i)}</span>" for i in dish.get("ingredients") or [])
                parts.append(
                    f'<div class=dish><div class=dishhead><b>{html.escape(dish["name"])}</b>'
                    f'<form class=delform method=post action="{BASE}/dishes/delete">'
                    f'<input type=hidden name=name value="{html.escape(dish["name"])}">'
                    f'<button class=delbtn title=remove>✕</button></form></div>'
                    f'<div class=pills>{pills}</div></div>'
                )
            rows = "".join(parts)

        chips = _ingredient_chip_groups(cfg.get("ingredients") or [], set(), field="ingredients", idprefix="di")
        body = f"""
        <p class=sub>Everything we know how to cook. Add your own below.</p>
        {rows}
        <div class=grouplabel style="margin-top:24px">Add a dish</div>
        <form method=post action="{BASE}/dishes/add">
          <input type=text name=name placeholder="Dish name, e.g. Chicken Chettinad" maxlength=60 required>
          {chips}
          <button type=submit class=cta>Add dish</button>
        </form>
        """
        return _page("Dish Library", body, back=f"{BASE}/")

    @router.post("/dishes/add")
    async def dishes_add(request: Request) -> RedirectResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()[:60]
        ingredients = list(form.getlist("ingredients"))
        if name and ingredients:
            cfg = _config()
            dishes = list(cfg.get("dishes") or [])
            if not any(d["name"].lower() == name.lower() for d in dishes):
                dishes.append({"name": name, "ingredients": ingredients})
                _set({"dishes": dishes})
        return RedirectResponse(f"{BASE}/dishes", status_code=303)

    @router.post("/dishes/delete")
    def dishes_delete(name: str = Form(...)) -> RedirectResponse:
        cfg = _config()
        dishes = [d for d in (cfg.get("dishes") or []) if d["name"] != name]
        menu = {d: [n for n in (v or []) if n != name] for d, v in (cfg.get("menu") or {}).items()}
        _set({"dishes": dishes, "menu": menu})
        return RedirectResponse(f"{BASE}/dishes", status_code=303)

    # ---------- weekly menu ----------

    @router.get("/menu", response_class=HTMLResponse)
    def menu_index() -> HTMLResponse:
        cfg = _config()
        menu = cfg.get("menu") or {}
        today = today_day()
        rows = []
        for d in DAYS:
            items = menu.get(d) or []
            summary = ", ".join(items) if items else "nothing planned"
            mark = " ⭐" if d == today else ""
            rows.append(
                f'<a class=menurow href="{BASE}/menu/{d}"><span class=d>{d.capitalize()}{mark}</span>'
                f"<span class=s>{html.escape(summary)}</span></a>"
            )
        body = f"""
        <p class=sub>Tap a day to add or remove dishes.</p>
        {"".join(rows)}
        """
        return _page("Weekly Menu", body, back=f"{BASE}/")

    @router.get("/menu/{day}", response_class=HTMLResponse)
    def menu_day_page(day: str) -> HTMLResponse:
        if day not in DAYS:
            return RedirectResponse(f"{BASE}/menu", status_code=303)
        cfg = _config()
        assigned = set((cfg.get("menu") or {}).get(day) or [])
        dishes = cfg.get("dishes") or []
        ready = {
            d["name"]
            for d in suggest_dishes(cfg.get("ingredients") or [], dishes, cfg.get("available") or [], max_missing=0)
        }
        ordered = sorted(dishes, key=lambda d: (d["name"] not in ready, d["name"]))

        pills = []
        for dish in ordered:
            name = dish["name"]
            on = name in assigned
            pills.append(
                f"""<form method=post action="{BASE}/menu/toggle">
                  <input type=hidden name=dish value="{html.escape(name)}">
                  <input type=hidden name=day value="{day}">
                  <input type=hidden name=next value="menu/{day}">
                  <button class="pillbtn{' on' if on else ''}">{html.escape(name)}{' ✕' if on else ''}</button>
                </form>"""
            )
        body = f"""
        <p class=sub>Click a dish to add it; click an added one again to remove it. Ready-to-cook dishes are listed first.</p>
        <div class=pillbtns>{"".join(pills)}</div>
        """
        return _page(day.capitalize(), body, back=f"{BASE}/menu")

    @router.post("/menu/toggle")
    def menu_toggle(
        dish: str = Form(...), day: str = Form(...), next_path: str = Form(f"{BASE}/", alias="next")
    ) -> RedirectResponse:
        _toggle_menu(day, dish)
        target = next_path if next_path.startswith("/") else f"{BASE}/{next_path}"
        return RedirectResponse(target, status_code=303)

    # ---------- backup / restore ----------

    @router.get("/export")
    def export_backup() -> Response:
        """Download the whole Home Chef config as a JSON file to keep off-device."""
        payload = {
            "app": "homechef",
            "version": 1,
            "exported": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "config": _config(),
        }
        fname = f"homechef-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        return Response(
            json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    @router.get("/restore", response_class=HTMLResponse)
    def restore_page() -> HTMLResponse:
        body = f"""
        <p class=sub>Upload a backup file to replace your pantry, dish library, and weekly menu.</p>
        <form method=post action="{BASE}/restore" enctype="multipart/form-data">
          <input type=file name=backup accept="application/json,.json" required
                 style="width:100%;padding:12px;background:#0c0d11;border:1px solid var(--border);border-radius:11px;color:var(--text);margin-bottom:10px">
          <button type=submit class=cta>Restore from backup</button>
        </form>
        <p class=hint>This replaces everything in Home Chef with the file's contents. Download a backup first (from the home screen) if you want to keep the current data.</p>
        """
        return _page("Restore Backup", body, back=f"{BASE}/")

    @router.post("/restore")
    async def restore_do(backup: UploadFile = File(...)):
        """Restore from a file produced by /export (or a raw homechef config)."""
        msg = "Couldn't read that file."
        try:
            data = json.loads((await backup.read()).decode("utf-8"))
            cfg = data["config"] if isinstance(data, dict) and isinstance(data.get("config"), dict) else data
            if isinstance(cfg, dict) and all(k in cfg for k in ("ingredients", "dishes", "menu")):
                _set({
                    "ingredients": list(cfg.get("ingredients") or []),
                    "dishes": list(cfg.get("dishes") or []),
                    "available": list(cfg.get("available") or []),
                    "menu": {d: list((cfg.get("menu") or {}).get(d) or []) for d in DAYS},
                })
                return RedirectResponse(f"{BASE}/?restored=1", status_code=303)
            msg = "That file isn't a Home Chef backup (it needs ingredients, dishes, and menu)."
        except (ValueError, UnicodeDecodeError, KeyError):
            msg = "That file isn't valid JSON."
        return _page("Restore failed", f"<p class=hint>{html.escape(msg)}</p>", back=f"{BASE}/restore")

    return router
