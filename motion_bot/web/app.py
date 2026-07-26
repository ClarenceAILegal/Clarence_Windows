"""FastAPI app: private Clarence website."""

from __future__ import annotations

import json
import re
import shutil
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
from motion_bot.generator import generate_motion
from motion_bot.models import motion_from_dict
from motion_bot.paths import OUTPUT_DIR, ensure_runtime_dirs
from motion_bot.web.auth import (
    consume_intro_flag,
    get_session_secret,
    is_authenticated,
    login_session,
    logout_session,
    verify_password,
)
from motion_bot.web.search import search_templates

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_HTML = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")

app = FastAPI(title="Clarence", version=__version__, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
    session_cookie="motion_bot_session",
    same_site="lax",
    https_only=False,
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
    ctx = {
        "request": request,
        "authed": _authed(request),
        "version": __version__,
        "flashes": _pop_flashes(request),
        "play_intro": False,
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
async def home(request: Request, q: str = "", awakened: Optional[str] = None):
    if not _authed(request):
        return _redirect_login()
    # Play water-ripple intro once after successful login
    play_intro = consume_intro_flag(request)
    query = (q or "").strip()
    results = search_templates(query) if query else []
    return templates.TemplateResponse(
        "home.html",
        _base_ctx(
            request,
            query=query,
            results=results,
            play_intro=play_intro,
        ),
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
async def generate_page(request: Request, template_id: Optional[str] = None):
    if not _authed(request):
        return _redirect_login()
    entries = list_templates()
    selected = None
    placeholders: List[str] = []
    if template_id:
        try:
            selected = get_template(template_id)
            placeholders = list(selected.placeholders) or refresh_placeholders(
                template_id
            ).placeholders
        except (KeyError, FileNotFoundError):
            selected = None
    return templates.TemplateResponse(
        "generate.html",
        _base_ctx(
            request,
            entries=entries,
            selected=selected,
            placeholders=placeholders,
            today=date.today().isoformat(),
            form_defaults={},
            error=None,
        ),
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

    _flash(request, f"Generated {out_path.name}", "success")
    return RedirectResponse(url=f"/download/{out_path.name}", status_code=303)


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
        _flash(request, "File not found.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse(
        path,
        filename=safe,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


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

    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        return templates.TemplateResponse(
            "upload.html",
            _upload_ctx(
                request,
                error="Only .docx files are supported. Convert PDFs to .docx first.",
                suggested_query=suggested,
                next_url=next_url,
                form_defaults=form_defaults,
            ),
            status_code=400,
        )

    suffix = Path(filename).suffix or ".docx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        # Always copy into templates/library and register in the catalog.
        entry = import_template(
            tmp_path,
            template_id=template_id.strip() or None,
            name=name.strip() or None,
            description=(
                description.strip()
                or suggested
                or f"Uploaded template ({filename})"
            ),
            jurisdiction=jurisdiction.strip(),
            motion_type=motion_type.strip(),
            notes="Uploaded via Clarence and automatically added to the library.",
        )
    except Exception as exc:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
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
    finally:
        tmp_path.unlink(missing_ok=True)

    _flash(
        request,
        f"Added to library: {entry.name}. You can search for it or generate a motion.",
        "success",
    )
    # Prefer template page so user sees it was catalogued; optional return to search
    if suggested:
        return RedirectResponse(
            url=f"/home?q={quote(suggested)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/templates/{entry.id}", status_code=303)


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


def create_app() -> FastAPI:
    return app
