"""FastAPI app: private Clarence website."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from motion_bot import __version__
from motion_bot.catalog import (
    get_template,
    import_template,
    list_templates,
    refresh_placeholders,
)
from motion_bot.compose import compose_motion_request, form_defaults_for_template
from motion_bot.generator import generate_motion
from motion_bot.models import motion_from_dict
from motion_bot.paths import OUTPUT_DIR, ensure_runtime_dirs
from motion_bot.grok_chat import clarence_reply, grok_available
from motion_bot.query_parse import parse_user_query
from motion_bot.settings import (
    clear_xai_api_key,
    get_xai_api_key,
    is_grok_chat_enabled,
    mask_api_key,
    set_grok_chat_enabled,
    set_xai_api_key,
    settings_path,
)
from motion_bot.web.auth import (
    consume_intro_flag,
    get_session_secret,
    is_authenticated,
    login_session,
    logout_session,
    use_https_cookies,
    verify_password,
)
from motion_bot.web.search import search_templates

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_HTML = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _is_desktop() -> bool:
    return os.environ.get("CLARENCE_DESKTOP", "").strip() in ("1", "true", "yes", "on")


def _downloads_dir() -> Path:
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "Download",
    ]
    # Windows: respect user profile Downloads
    if platform.system() == "Windows":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            candidates.insert(0, Path(userprofile) / "Downloads")
    for c in candidates:
        if c.is_dir():
            return c
    # Fall back to project output if Downloads missing
    ensure_runtime_dirs()
    return OUTPUT_DIR


def _copy_to_downloads(path: Path) -> Path:
    """Copy generated motion into the user's Downloads folder."""
    dest_dir = _downloads_dir()
    dest = dest_dir / path.name
    # Avoid clobbering: if exists, add a short suffix
    if dest.exists():
        stem = path.stem
        dest = dest_dir / f"{stem}_copy{path.suffix}"
        n = 2
        while dest.exists():
            dest = dest_dir / f"{stem}_copy{n}{path.suffix}"
            n += 1
    shutil.copy2(path, dest)
    return dest


def _open_path(path: Path, *, reveal: bool = False) -> None:
    """Open or reveal a file in the OS file manager / default app (best-effort)."""
    try:
        system = platform.system()
        if system == "Darwin":
            if reveal:
                subprocess.Popen(["open", "-R", str(path)])  # noqa: S603
            else:
                subprocess.Popen(["open", str(path)])  # noqa: S603
        elif system == "Windows":
            if reveal:
                # Open Explorer with the file selected
                subprocess.Popen(  # noqa: S603
                    ["explorer", f"/select,{path}"]
                )
            else:
                os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603
    except Exception:
        pass


def _finish_generation(
    request: Request,
    out_path: Path,
    *,
    template_name: str = "",
) -> HTMLResponse:
    """
    After a motion is written: copy to Downloads, open on desktop, show success page.

    pywebview (desktop) does not reliably handle Content-Disposition downloads, so we
    never leave the user on a blank binary response.
    """
    ensure_runtime_dirs()
    downloads_copy: Optional[Path] = None
    try:
        downloads_copy = _copy_to_downloads(out_path)
    except Exception:
        downloads_copy = None

    # Desktop: open the document in Word/Pages/etc. immediately
    open_target = downloads_copy or out_path
    if _is_desktop():
        _open_path(open_target, reveal=False)

    _flash(
        request,
        f"Generated “{out_path.name}”"
        + (f" · also saved to Downloads" if downloads_copy else ""),
        "success",
    )
    return templates.TemplateResponse(
        "generated.html",
        _base_ctx(
            request,
            filename=out_path.name,
            output_path=str(out_path),
            downloads_name=(downloads_copy.name if downloads_copy else ""),
            downloads_path=(str(downloads_copy) if downloads_copy else ""),
            template_name=template_name,
            is_desktop=_is_desktop(),
        ),
    )

app = FastAPI(title="Clarence", version=__version__, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
    session_cookie="motion_bot_session",
    same_site="lax",
    https_only=use_https_cookies(),
    max_age=60 * 60 * 12,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_HTML))


def _authed(request: Request) -> bool:
    return is_authenticated(request)


def _redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


def _flash(request: Request, message: str, level: str = "info") -> None:
    flashes = request.session.get("flashes") or []
    flashes.append({"message": message, "level": level})
    request.session["flashes"] = flashes


def _pop_flashes(request: Request) -> List[Dict[str, str]]:
    flashes = request.session.pop("flashes", []) or []
    return list(flashes)


def _base_ctx(request: Request, **extra: Any) -> Dict[str, Any]:
    grok_key = grok_available()
    grok_on = is_grok_chat_enabled()
    ctx = {
        "request": request,
        "authed": _authed(request),
        "version": __version__,
        "flashes": _pop_flashes(request),
        "play_intro": False,
        # Key is per-user/machine; only grok_chat_on means chat may bill.
        "grok_key_present": grok_key,
        "grok_chat_on": grok_on,
        "grok_enabled": grok_key and grok_on,
        "grok_key_masked": mask_api_key() if grok_key else "",
    }
    ctx.update(extra)
    return ctx


@app.on_event("startup")
def _startup() -> None:
    ensure_runtime_dirs()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not _authed(request):
        return _redirect_login()
    return RedirectResponse(url="/home", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _authed(request):
        return RedirectResponse(url="/home", status_code=303)
    return templates.TemplateResponse(
        "login.html", _base_ctx(request, error=None)
    )


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    wants_json = "application/json" in (request.headers.get("accept") or "")
    if verify_password(password):
        login_session(request, play_intro=True)
        if wants_json:
            return JSONResponse({"ok": True, "redirect": "/home?awakened=1"})
        return RedirectResponse(url="/home?awakened=1", status_code=303)

    if wants_json:
        return JSONResponse(
            {"ok": False, "error": "Incorrect password."},
            status_code=401,
        )
    return templates.TemplateResponse(
        "login.html",
        _base_ctx(request, error="Incorrect password."),
        status_code=401,
    )


@app.post("/logout")
async def logout(request: Request):
    logout_session(request)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/home", response_class=HTMLResponse)
async def home(
    request: Request,
    q: str = "",
    mode: str = "search",
    template_id: str = "",
    awakened: Optional[str] = None,
):
    if not _authed(request):
        return _redirect_login()
    # Play water-ripple intro once after successful login
    play_intro = consume_intro_flag(request)
    query = (q or "").strip()
    mode = (mode or "chat").strip().lower()
    if mode not in ("chat", "search", "generate"):
        mode = "chat"
    forced_tid = (template_id or "").strip()

    # Chat / free-text: extract fields for matching; don't force generate from verbs alone
    parsed = (
        parse_user_query(query, force_intent="search" if mode == "chat" else mode)
        if query
        else None
    )
    search_q = parsed.search_text if parsed else ""
    results = search_templates(search_q) if search_q else []

    # One-shot generate (after user chooses in chat)
    if query and mode == "generate":
        best_entry = None
        if forced_tid:
            try:
                best_entry = get_template(forced_tid)
            except (KeyError, FileNotFoundError):
                best_entry = None
        if best_entry is None and results:
            best_entry = results[0][0]
        if best_entry is None:
            return templates.TemplateResponse(
                "home.html",
                _base_ctx(
                    request,
                    query=query,
                    results=[],
                    play_intro=play_intro,
                    mode="generate",
                    generate_error=(
                        "I couldn’t generate that yet because there’s no matching "
                        "template in your library."
                    ),
                    extracted={},
                    show_chat=True,
                    best_template_id="",
                    best_template_name="",
                ),
            )
        try:
            motion_req = compose_motion_request(best_entry, parsed)
            out_path = generate_motion(motion_req)
        except Exception as exc:  # noqa: BLE001
            return templates.TemplateResponse(
                "home.html",
                _base_ctx(
                    request,
                    query=query,
                    results=results,
                    play_intro=play_intro,
                    mode="generate",
                    generate_error=f"Could not generate: {exc}",
                    extracted=parsed.fields if parsed else {},
                    show_chat=True,
                    offer_generate=bool(results),
                    offer_form=bool(results),
                    offer_upload=not bool(results),
                    best_template_id=(best_entry.id if best_entry else ""),
                    best_template_name=(best_entry.name if best_entry else ""),
                    chat_message="",
                    chat_engine="free (built-in)",
                ),
                status_code=400,
            )
        return _finish_generation(
            request, out_path, template_name=best_entry.name
        )

    extracted = parsed.fields if parsed else {}
    # Grok only for conversational chat when the user has turned it ON.
    # mode=generate (one-shot) returns earlier and never bills.
    # Form path is a separate POST and never bills.
    chat = None
    if query:
        chat = clarence_reply(
            query,
            results,
            extracted,
            use_grok=is_grok_chat_enabled(),
        )

    best_id = ""
    best_name = ""
    if chat and chat.best_template_id:
        best_id = chat.best_template_id
        best_name = chat.best_template_name
    elif results:
        best_id = results[0][0].id
        best_name = results[0][0].name

    # If Grok/rules say upload-only, hide weak false matches from the UI
    display_results = results
    if chat and chat.offer_upload and not chat.offer_generate and not chat.offer_form:
        display_results = []
        best_id = ""
        best_name = ""

    engine_label = chat.source if chat else "rules"
    if engine_label == "rules":
        engine_label = "free (built-in)"
    elif engine_label == "grok":
        engine_label = "Grok (API)"

    return templates.TemplateResponse(
        "home.html",
        _base_ctx(
            request,
            query=query,
            results=display_results,
            play_intro=play_intro,
            mode=mode,
            generate_error=None,
            extracted=extracted,
            show_chat=bool(query),
            best_template_id=best_id,
            best_template_name=best_name,
            chat_message=(chat.message if chat else ""),
            offer_generate=bool(chat.offer_generate) if chat else False,
            offer_form=bool(chat.offer_form) if chat else False,
            offer_upload=bool(chat.offer_upload) if chat else False,
            chat_engine=engine_label,
        ),
    )


@app.get("/api/settings")
async def api_get_settings(request: Request):
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    return JSONResponse(
        {
            "ok": True,
            "grok_chat_enabled": is_grok_chat_enabled(),
            "grok_key_present": grok_available(),
            "grok_key_masked": mask_api_key(),
            "settings_path": str(settings_path()),
            "note": (
                "Each person must add their own Grok API key on their computer. "
                "Keys are stored only on this Mac and are never shared. "
                "One-shot generate and form fill never call Grok."
            ),
        }
    )


@app.post("/api/settings/grok")
async def api_set_grok(request: Request):
    """Toggle Grok for chat only. Default is off (no API charges)."""
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    enabled: Optional[bool] = None
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if isinstance(body, dict) and "enabled" in body:
            enabled = bool(body.get("enabled"))
    else:
        form = await request.form()
        raw = form.get("enabled")
        if raw is not None:
            enabled = str(raw).strip().lower() in ("1", "true", "yes", "on")

    if enabled is None:
        return JSONResponse(
            {"ok": False, "error": "missing enabled"},
            status_code=400,
        )

    saved = set_grok_chat_enabled(enabled)
    return JSONResponse(
        {
            "ok": True,
            "grok_chat_enabled": bool(saved.get("grok_chat_enabled")),
            "grok_key_present": grok_available(),
            "grok_key_masked": mask_api_key(),
            "billing": (
                "Chat may use paid Grok API"
                if saved.get("grok_chat_enabled") and grok_available()
                else "Free built-in chat (no API charges)"
            ),
        }
    )


@app.post("/api/settings/api-key")
async def api_set_api_key(request: Request):
    """Save this user's private xAI API key (this computer only)."""
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        body = {}

    if body.get("clear"):
        clear_xai_api_key()
        # If Grok was on, leave toggle as-is but it won't bill without a key
        return JSONResponse(
            {
                "ok": True,
                "grok_key_present": False,
                "grok_key_masked": "",
                "message": "API key removed from this computer.",
            }
        )

    key = str(body.get("key") or body.get("api_key") or "").strip()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Paste your xAI API key."},
            status_code=400,
        )
    if len(key) < 12:
        return JSONResponse(
            {"ok": False, "error": "That does not look like a valid API key."},
            status_code=400,
        )

    set_xai_api_key(key)
    return JSONResponse(
        {
            "ok": True,
            "grok_key_present": True,
            "grok_key_masked": mask_api_key(),
            "message": (
                "API key saved on this computer only. "
                "Other people need their own key on their machines."
            ),
        }
    )


@app.get("/library", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _authed(request):
        return _redirect_login()
    entries = list_templates()
    outputs = sorted(OUTPUT_DIR.glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return templates.TemplateResponse(
        "dashboard.html",
        _base_ctx(
            request,
            entries=entries,
            outputs=[{"name": p.name, "size": p.stat().st_size} for p in outputs[:25]],
        ),
    )


@app.get("/templates/{template_id}", response_class=HTMLResponse)
async def template_detail(request: Request, template_id: str):
    if not _authed(request):
        return _redirect_login()
    try:
        entry = refresh_placeholders(template_id)
    except KeyError as exc:
        _flash(request, str(exc), "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        "template_detail.html",
        _base_ctx(request, entry=entry),
    )


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(
    request: Request,
    template_id: Optional[str] = None,
    q: str = "",
):
    if not _authed(request):
        return _redirect_login()
    entries = list_templates()
    selected = None
    placeholders: List[str] = []
    form_defaults: Dict[str, Any] = {}

    # Prefill from session (set by "Edit form" actions) or free-text q=
    session_prefill = request.session.pop("generate_prefill", None)
    if isinstance(session_prefill, dict):
        form_defaults.update(session_prefill)
        if not template_id:
            template_id = session_prefill.get("template_id") or template_id

    query = (q or "").strip()
    if template_id:
        try:
            selected = get_template(template_id)
            placeholders = list(selected.placeholders) or refresh_placeholders(
                template_id
            ).placeholders
        except (KeyError, FileNotFoundError):
            selected = None

    if query:
        parsed = parse_user_query(query, force_intent="search")
        if selected:
            form_defaults = {
                **form_defaults_for_template(selected, parsed),
                **form_defaults,
            }
        else:
            # Pick best template for the query if none selected
            hits = search_templates(parsed.search_text)
            if hits:
                selected = hits[0][0]
                template_id = selected.id
                placeholders = list(selected.placeholders)
                form_defaults = {
                    **form_defaults_for_template(selected, parsed),
                    **form_defaults,
                }
            else:
                form_defaults = {**form_defaults, **parsed.fields}

    if selected and not form_defaults.get("motion_title"):
        form_defaults["motion_title"] = selected.name

    return templates.TemplateResponse(
        "generate.html",
        _base_ctx(
            request,
            entries=entries,
            selected=selected,
            placeholders=placeholders,
            today=date.today().isoformat(),
            form_defaults=form_defaults,
            error=None,
            seed_query=query,
        ),
    )


@app.post("/prepare-form")
async def prepare_form(
    request: Request,
    q: str = Form(""),
    template_id: str = Form(""),
):
    """Search-bar path: open generate form prefilled from free text + template."""
    if not _authed(request):
        return _redirect_login()
    query = (q or "").strip()
    tid = (template_id or "").strip()
    parsed = parse_user_query(query, force_intent="search")
    try:
        entry = get_template(tid) if tid else None
    except (KeyError, FileNotFoundError):
        entry = None
    if entry is None and query:
        hits = search_templates(parsed.search_text)
        entry = hits[0][0] if hits else None
    if entry is None:
        _flash(request, "Pick or upload a template first.", "error")
        return RedirectResponse(
            url=f"/home?q={quote(query)}" if query else "/home",
            status_code=303,
        )
    prefill = form_defaults_for_template(entry, parsed)
    request.session["generate_prefill"] = prefill
    return RedirectResponse(
        url=f"/generate?template_id={quote(entry.id)}",
        status_code=303,
    )


def _build_case_payload(form: Dict[str, Any]) -> Dict[str, Any]:
    template_id = (form.get("template_id") or "").strip()
    if not template_id:
        raise ValueError("Template is required.")

    custom_raw = (form.get("custom_yaml") or "").strip()
    custom: Dict[str, Any] = {}
    if custom_raw:
        loaded = yaml.safe_load(custom_raw)
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            raise ValueError("Custom fields must be a YAML/JSON object (key: value).")
        custom = loaded

    # Promote common custom keys used by FL motion templates when provided in form
    for key in (
        "defendant_name",
        "judicial_circuit",
        "court_level",
        "eyewitness_name",
        "officer_name",
        "identification_date",
        "identification_place",
        "charged_offense",
        "suppression_relief",
        "charging_date",
        "current_trial_date",
        "requested_continuance_date",
        "additional_grounds",
        "service_date",
        "identification_medium",
        "suggestive_procedure",
    ):
        val = (form.get(key) or "").strip()
        if val:
            custom[key] = val

    payload: Dict[str, Any] = {
        "template_id": template_id,
        "motion_title": (form.get("motion_title") or "Motion").strip(),
        "caption": {
            "court_name": (form.get("court_name") or "").strip(),
            "court_division": (form.get("court_division") or "").strip(),
            "county": (form.get("county") or "").strip(),
            "state": (form.get("state") or "Florida").strip(),
            "case_number": (form.get("case_number") or "").strip(),
            "judge": (form.get("judge") or "").strip(),
            "plaintiff": (form.get("plaintiff") or "").strip(),
            "defendant": (form.get("defendant") or form.get("defendant_name") or "").strip(),
        },
        "movant": {
            "name": (form.get("movant_name") or form.get("defendant_name") or "").strip(),
            "role": (form.get("movant_role") or "Defendant").strip(),
            "counsel": (form.get("counsel_name") or "").strip(),
            "bar_number": (form.get("counsel_bar") or "").strip(),
            "firm": (form.get("counsel_firm") or "").strip(),
            "address": (form.get("counsel_address") or "").strip(),
            "phone": (form.get("counsel_phone") or "").strip(),
            "email": (form.get("counsel_email") or "").strip(),
        },
        "filing_date": (form.get("filing_date") or date.today().isoformat()).strip(),
        "factual_background": (form.get("factual_background") or "").strip(),
        "legal_argument": (form.get("legal_argument") or "").strip(),
        "prayer_for_relief": (form.get("prayer_for_relief") or "").strip(),
        "certificate_of_service": (form.get("certificate_of_service") or "").strip(),
        "relief_sought": (form.get("relief_sought") or "").strip(),
        "custom": custom,
    }
    return payload


@app.post("/generate")
async def generate_submit(request: Request):
    if not _authed(request):
        return _redirect_login()

    form = dict(await request.form())
    # Convert UploadFile / multi values to plain strings
    clean: Dict[str, Any] = {}
    for k, v in form.items():
        clean[k] = v if isinstance(v, str) else str(v)

    entries = list_templates()
    selected = None
    placeholders: List[str] = []
    template_id = clean.get("template_id") or ""
    if template_id:
        try:
            selected = get_template(template_id)
            placeholders = list(selected.placeholders)
        except (KeyError, FileNotFoundError):
            pass

    try:
        payload = _build_case_payload(clean)
        request_obj = motion_from_dict(payload)
        out_path = generate_motion(request_obj)
    except Exception as exc:  # noqa: BLE001 - show to authenticated user
        return templates.TemplateResponse(
            "generate.html",
            _base_ctx(
                request,
                entries=entries,
                selected=selected,
                placeholders=placeholders,
                today=date.today().isoformat(),
                form_defaults=clean,
                error=str(exc),
            ),
            status_code=400,
        )

    return _finish_generation(
        request,
        out_path,
        template_name=(selected.name if selected else ""),
    )


@app.get("/download/{filename}")
async def download_file(request: Request, filename: str):
    if not _authed(request):
        return _redirect_login()
    # Prevent path traversal
    safe = Path(filename).name
    if SAFE_ID_RE.search(safe) or not safe.endswith(".docx"):
        _flash(request, "Invalid file name.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    path = OUTPUT_DIR / safe
    if not path.exists() or not path.is_file():
        # Also allow files that only live in Downloads (desktop copy)
        dl = _downloads_dir() / safe
        if dl.exists() and dl.is_file():
            path = dl
        else:
            _flash(request, "File not found.", "error")
            return RedirectResponse(url="/library", status_code=303)
    headers = {
        "Content-Disposition": f'attachment; filename="{safe}"',
        "Cache-Control": "no-store",
    }
    return FileResponse(
        path,
        filename=safe,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@app.post("/api/reveal-file")
async def api_reveal_file(request: Request):
    """Desktop helper: reveal a generated file in Finder."""
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    name = Path(str((body or {}).get("filename") or "")).name
    if not name or SAFE_ID_RE.search(name) or not name.endswith(".docx"):
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
    for candidate in (OUTPUT_DIR / name, _downloads_dir() / name):
        if candidate.exists():
            _open_path(candidate, reveal=True)
            return JSONResponse({"ok": True, "path": str(candidate)})
    return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)


@app.post("/api/open-file")
async def api_open_file(request: Request):
    """Desktop helper: open a generated .docx in the default app."""
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    name = Path(str((body or {}).get("filename") or "")).name
    if not name or SAFE_ID_RE.search(name) or not name.endswith(".docx"):
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
    for candidate in (_downloads_dir() / name, OUTPUT_DIR / name):
        if candidate.exists():
            _open_path(candidate, reveal=False)
            return JSONResponse({"ok": True, "path": str(candidate)})
    return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)


def _upload_ctx(
    request: Request,
    *,
    error: Optional[str] = None,
    suggested_query: str = "",
    next_url: str = "/home",
    form_defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _base_ctx(
        request,
        error=error,
        suggested_query=suggested_query or "",
        next_url=next_url or "/home",
        form_defaults=form_defaults or {},
    )


def _import_uploaded_docx(
    upload: UploadFile,
    *,
    template_id: str = "",
    name: str = "",
    description: str = "",
    jurisdiction: str = "FL",
    motion_type: str = "",
    suggested: str = "",
):
    """Save upload to temp, import into library, return TemplateEntry. Raises ValueError."""
    filename = upload.filename or ""
    if not filename.lower().endswith(".docx"):
        raise ValueError("Only .docx files are supported. Convert PDFs to .docx first.")

    suffix = Path(filename).suffix or ".docx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(upload.file, tmp)

    try:
        return import_template(
            tmp_path,
            template_id=template_id.strip() or None,
            name=name.strip() or None,
            description=(
                description.strip()
                or suggested.strip()
                or f"Uploaded template ({filename})"
            ),
            jurisdiction=(jurisdiction or "FL").strip(),
            motion_type=motion_type.strip(),
            notes="Uploaded via Clarence and automatically added to the library.",
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    q: str = "",
    next: str = "/home",  # noqa: A002 — query param name
):
    if not _authed(request):
        return _redirect_login()
    suggested = (q or "").strip()
    # Safe internal redirect only
    next_url = next if next.startswith("/") and not next.startswith("//") else "/home"
    return templates.TemplateResponse(
        "upload.html",
        _upload_ctx(
            request,
            suggested_query=suggested,
            next_url=next_url,
            form_defaults={
                "name": suggested,
                "description": suggested,
            },
        ),
    )


@app.post("/upload")
async def upload_submit(
    request: Request,
    file: UploadFile = File(...),
    template_id: str = Form(""),
    name: str = Form(""),
    jurisdiction: str = Form("FL"),
    motion_type: str = Form(""),
    description: str = Form(""),
    next: str = Form("/home"),  # noqa: A002
    suggested_query: str = Form(""),
):
    if not _authed(request):
        return _redirect_login()

    next_url = next if next.startswith("/") and not next.startswith("//") else "/home"
    suggested = (suggested_query or "").strip()
    form_defaults = {
        "template_id": template_id,
        "name": name,
        "jurisdiction": jurisdiction,
        "motion_type": motion_type,
        "description": description,
    }

    try:
        entry = _import_uploaded_docx(
            file,
            template_id=template_id,
            name=name,
            description=description,
            jurisdiction=jurisdiction,
            motion_type=motion_type,
            suggested=suggested,
        )
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(
            "upload.html",
            _upload_ctx(
                request,
                error=str(exc),
                suggested_query=suggested,
                next_url=next_url,
                form_defaults=form_defaults,
            ),
            status_code=400,
        )

    _flash(
        request,
        f"Added to library: {entry.name}. You can search for it or generate a motion.",
        "success",
    )
    if suggested:
        return RedirectResponse(
            url=f"/home?q={quote(suggested)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/templates/{entry.id}", status_code=303)


@app.post("/api/upload")
async def api_upload(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
    jurisdiction: str = Form("FL"),
    motion_type: str = Form(""),
    suggested_query: str = Form(""),
):
    """Drag-and-drop upload: always adds .docx to the library. Returns JSON."""
    if not _authed(request):
        return JSONResponse({"ok": False, "error": "Not authenticated."}, status_code=401)

    suggested = (suggested_query or "").strip()
    try:
        entry = _import_uploaded_docx(
            file,
            name=name,
            description=description,
            jurisdiction=jurisdiction,
            motion_type=motion_type,
            suggested=suggested,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return JSONResponse(
        {
            "ok": True,
            "id": entry.id,
            "name": entry.name,
            "description": entry.description,
            "jurisdiction": entry.jurisdiction,
            "motion_type": entry.motion_type,
            "source": entry.source,
            "message": f"Added to library: {entry.name}",
        }
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


def create_app() -> FastAPI:
    return app
