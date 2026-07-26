"""Generate filled motion Word documents from templates + case data."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from docxtpl import DocxTemplate

from motion_bot.catalog import TemplateEntry, get_template
from motion_bot.models import MotionRequest
from motion_bot.paths import OUTPUT_DIR, ensure_runtime_dirs

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_filename(parts: list[str]) -> str:
    cleaned = []
    for part in parts:
        part = SAFE_NAME_RE.sub("_", part.strip()).strip("._")
        if part:
            cleaned.append(part)
    return "_".join(cleaned) or "motion"


def generate_motion(
    request: MotionRequest,
    *,
    output_path: Path | None = None,
    template: TemplateEntry | None = None,
) -> Path:
    """
    Fill a registered .docx template with case data and write a finished motion.

    Templates use Jinja2 placeholders (docxtpl), e.g. {{ case_number }}, {{ motion_title }}.
    """
    ensure_runtime_dirs()
    entry = template or get_template(request.template_id)
    if not entry.path.exists():
        raise FileNotFoundError(f"Template file not found: {entry.path}")

    context = request.to_context()
    doc = DocxTemplate(str(entry.path))
    doc.render(context)

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = _safe_filename(
            [
                request.caption.case_number or "case",
                request.motion_title or entry.id,
                stamp,
            ]
        )
        output_path = OUTPUT_DIR / f"{base}.docx"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    doc.save(str(output_path))
    return output_path
