"""Compose a MotionRequest from a template + parsed free-text fields."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from motion_bot.catalog import TemplateEntry
from motion_bot.models import CaseCaption, MotionRequest, Party, motion_from_dict
from motion_bot.query_parse import ParsedQuery, parsed_to_form_defaults


def compose_motion_request(
    template: TemplateEntry,
    parsed: ParsedQuery,
    *,
    extra_form: Optional[Dict[str, Any]] = None,
) -> MotionRequest:
    """Build a filled MotionRequest for generation."""
    defaults = parsed_to_form_defaults(parsed, template_name=template.name)
    if extra_form:
        for k, v in extra_form.items():
            if v not in (None, ""):
                defaults[k] = v

    defaults["template_id"] = template.id
    if not defaults.get("motion_title"):
        defaults["motion_title"] = template.name

    # Ensure defendant / movant linkage
    defendant = defaults.get("defendant_name") or ""
    if defendant and not defaults.get("movant_name"):
        defaults["movant_name"] = defendant

    # Put unused narrative into factual_background if still empty
    if not defaults.get("factual_background") and len(parsed.raw) > 20:
        defaults["factual_background"] = parsed.raw

    # Default certificate if missing
    if not defaults.get("certificate_of_service"):
        defaults["certificate_of_service"] = (
            "I certify that a true and correct copy of this Motion was served on all "
            "counsel of record via the Court's electronic filing system on the filing date."
        )

    if not defaults.get("filing_date"):
        defaults["filing_date"] = date.today().strftime("%B %d, %Y")

    # Map flat form defaults into nested structure for motion_from_dict
    payload: Dict[str, Any] = {
        "template_id": template.id,
        "motion_title": defaults.get("motion_title") or template.name,
        "caption": {
            "court_name": defaults.get("court_name", ""),
            "court_division": defaults.get("court_division", ""),
            "county": defaults.get("county", ""),
            "state": defaults.get("state", ""),
            "case_number": defaults.get("case_number", ""),
            "judge": defaults.get("judge", ""),
            "plaintiff": defaults.get("plaintiff", ""),
            "defendant": defaults.get("defendant_name", ""),
        },
        "movant": {
            "name": defaults.get("movant_name") or defaults.get("defendant_name") or "",
            "role": defaults.get("movant_role") or "Defendant",
            "counsel": defaults.get("counsel_name", ""),
            "bar_number": defaults.get("counsel_bar", ""),
            "firm": defaults.get("counsel_firm", ""),
            "address": defaults.get("counsel_address", ""),
            "phone": defaults.get("counsel_phone", ""),
            "email": defaults.get("counsel_email", ""),
        },
        "filing_date": defaults.get("filing_date", ""),
        "factual_background": defaults.get("factual_background", ""),
        "legal_argument": defaults.get("legal_argument", ""),
        "prayer_for_relief": defaults.get("prayer_for_relief", ""),
        "certificate_of_service": defaults.get("certificate_of_service", ""),
        "relief_sought": defaults.get("relief_sought", ""),
        "hearing_date": defaults.get("hearing_date", ""),
        "hearing_time": defaults.get("hearing_time", ""),
        "hearing_location": defaults.get("hearing_location", ""),
        "custom": {},
    }

    # FL template custom keys
    for key in (
        "court_level",
        "judicial_circuit",
        "defendant_name",
        "charging_date",
        "current_trial_date",
        "requested_continuance_date",
        "additional_grounds",
        "service_date",
        "eyewitness_name",
        "officer_name",
        "identification_date",
        "identification_place",
        "charged_offense",
        "identification_medium",
        "suggestive_procedure",
        "suppression_relief",
    ):
        if defaults.get(key):
            payload["custom"][key] = defaults[key]

    # custom_yaml from form/parser extras
    custom_yaml = defaults.get("custom_yaml")
    if custom_yaml:
        import yaml

        loaded = yaml.safe_load(custom_yaml)
        if isinstance(loaded, dict):
            payload["custom"].update(loaded)

    return motion_from_dict(payload)


def form_defaults_for_template(
    template: TemplateEntry,
    parsed: ParsedQuery,
) -> Dict[str, Any]:
    """Defaults for the HTML generate form."""
    d = parsed_to_form_defaults(parsed, template_name=template.name)
    d["template_id"] = template.id
    return d
