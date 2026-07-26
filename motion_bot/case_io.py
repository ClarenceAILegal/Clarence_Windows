"""Load and save case / motion input files (JSON or YAML)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from motion_bot.models import MotionRequest, motion_from_dict


def load_case_file(path: Path | str) -> MotionRequest:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        # Try YAML first, then JSON
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Case file must be a mapping/object: {path}")
    if "template_id" not in data:
        raise ValueError("Case file must include template_id")
    return motion_from_dict(data)


def dump_case_template(path: Path | str) -> Path:
    """Write a starter case YAML the user can edit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sample: dict[str, Any] = {
        "template_id": "sample-motion-to-compel",
        "motion_title": "Motion to Compel Discovery",
        "caption": {
            "court_name": "SUPERIOR COURT OF [STATE]",
            "court_division": "Civil Division",
            "county": "Example",
            "state": "State",
            "case_number": "CV-2026-000123",
            "judge": "Hon. Jane Doe",
            "plaintiff": "Acme Corporation",
            "defendant": "Jordan Smith",
        },
        "movant": {
            "name": "Acme Corporation",
            "role": "Plaintiff",
            "counsel": "Alex Counsel, Esq.",
            "bar_number": "123456",
            "firm": "Counsel & Associates LLP",
            "address": "100 Main Street, Suite 400, City, ST 00000",
            "phone": "(555) 555-0100",
            "email": "alex@counsel.example",
        },
        "respondent": {
            "name": "Jordan Smith",
            "role": "Defendant",
        },
        "hearing_date": "2026-09-15",
        "hearing_time": "9:00 a.m.",
        "hearing_location": "Courtroom 3B",
        "filing_date": "2026-07-25",
        "relief_sought": (
            "an order compelling Defendant to serve verified responses to "
            "Plaintiff's First Set of Interrogatories and produce documents "
            "responsive to Plaintiff's First Request for Production"
        ),
        "factual_background": (
            "On March 1, 2026, Plaintiff served written discovery on Defendant. "
            "Responses were due April 1, 2026. Despite a good-faith meet-and-confer "
            "on April 10, 2026, Defendant has not served responses or produced documents."
        ),
        "legal_argument": (
            "A party may move to compel discovery when the opposing party fails to "
            "respond. Defendant's failure prejudices Plaintiff's ability to prepare "
            "for trial. The Court should compel responses and award reasonable expenses."
        ),
        "prayer_for_relief": (
            "WHEREFORE, Movant respectfully requests that this Court enter an order: "
            "(1) compelling full discovery responses within 14 days; "
            "(2) awarding reasonable expenses including attorney's fees; and "
            "(3) granting such other relief as the Court deems just and proper."
        ),
        "certificate_of_service": (
            "I certify that on the filing date a true and correct copy of this Motion "
            "was served on all counsel of record via the Court's electronic filing system."
        ),
        "exhibits": [
            "Exhibit A — First Set of Interrogatories",
            "Exhibit B — Meet-and-Confer Correspondence",
        ],
        "custom": {},
    }
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(sample, fh, sort_keys=False, allow_unicode=True)
    return path
