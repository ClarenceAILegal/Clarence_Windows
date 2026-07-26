"""Parse free-text search / one-shot prompts into motion fields + intent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Optional


_GENERATE_HINTS = re.compile(
    r"\b("
    r"generate|draft|prepare|write|create|make|file|produce|one[\s-]?shot|"
    r"build\s+(?:the\s+)?motion|fill\s+(?:the\s+)?(?:motion|template)|"
    r"please\s+generate|generate\s+(?:it|this|the\s+motion)"
    r")\b",
    re.I,
)

_CASE_NO = re.compile(
    r"\b(?:case\s*(?:no\.?|number|#)?|case)\s*[:#]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9\-_/]{3,})",
    re.I,
)
_DEFENDANT = re.compile(
    r"\b(?:defendant|def\.?)\s*(?:is|:|-)?\s+([A-Z][^,.;\n]{1,80})",
)
_PLAINTIFF = re.compile(
    r"\b(?:plaintiff|pl\.?)\s*(?:is|:|-)?\s+([A-Z][^,.;\n]{1,80})",
)
_COUNTY = re.compile(r"\b([A-Z][a-zA-Z]+)\s+County\b")
_CIRCUIT = re.compile(
    r"\b((?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|"
    r"Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth|Sixteenth|Seventeenth|"
    r"Eighteenth|Nineteenth|Twentieth|\d+(?:st|nd|rd|th)?|"
    r"FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|"
    r"SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH))\s+"
    r"(?:Judicial\s+)?Circuit\b",
    re.I,
)
_JUDGE = re.compile(
    r"\b(?:Hon\.?|Judge)\s+([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,3})"
)
_COUNSEL = re.compile(
    r"\b(?:counsel|attorney|lawyer)\s*(?:is|:|-)?\s+"
    r"([A-Z][^,.;\n]{1,80}?)(?=\s*(?:,|;|\.|$|\bbar\b|\bflorida\b|\bfor\b))",
    re.I,
)
_BAR = re.compile(r"\b(?:Florida\s+)?Bar\s*(?:No\.?|Number|#)?\s*[:#]?\s*(\d{4,})", re.I)
_FIRM = re.compile(r"\bfirm\s*(?:is|:|-)?\s+([^,.;\n]{2,80})", re.I)
_PHONE = re.compile(r"\b(?:tel|phone|telephone)\s*(?:is|:|-)?\s*([+\d(][\d\s().-]{7,})", re.I)
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")
_TRIAL = re.compile(
    r"\b(?:trial|hearing)\s*(?:date|set\s+for|on)?\s*(?:is|:|-)?\s*"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.I,
)
_CHARGING = re.compile(
    r"\bcharg(?:ed|ing)\s*(?:on|date)?\s*(?:is|:|-)?\s*"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.I,
)
_OFFENSE = re.compile(
    r"\b(?:charged\s+with|offense\s*(?:is|:)|charge\s+of)\s+"
    r"([^,.;\n]{2,80})",
    re.I,
)
_EYEWITNESS = re.compile(
    r"\b(?:eyewitness|witness)\s*(?:is|:|-)?\s+([A-Z][^,.;\n]{1,60})",
)
_OFFICER = re.compile(
    r"\b(?:officer|det\.?|detective)\s*(?:is|:|-)?\s+([A-Z][^,.;\n]{1,60})",
)
_KV = re.compile(
    r"\b([a-z_][a-z0-9_]{1,40})\s*[:=]\s*[\"']?([^,\"'\n;]{1,120})[\"']?",
    re.I,
)

# Strip generate-intent phrases when building search text
_STRIP_GENERATE = re.compile(
    r"\b(?:please\s+)?(?:generate|draft|prepare|write|create|make|one[\s-]?shot)"
    r"(?:\s+(?:me|a|the|this|it|motion|for))?[\s,]*",
    re.I,
)


@dataclass
class ParsedQuery:
    raw: str
    intent: str  # "search" | "generate"
    search_text: str
    fields: Dict[str, str] = field(default_factory=dict)
    narrative: str = ""

    def get(self, key: str, default: str = "") -> str:
        return (self.fields.get(key) or default).strip()


def _clean_capture(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip(" \t\n\r,.;:\"'"))


def _set(fields: Dict[str, str], key: str, value: Optional[str]) -> None:
    if not value:
        return
    cleaned = _clean_capture(value)
    if cleaned and key not in fields:
        fields[key] = cleaned


def detect_generate_intent(text: str) -> bool:
    return bool(_GENERATE_HINTS.search(text or ""))


def parse_user_query(text: str, *, force_intent: Optional[str] = None) -> ParsedQuery:
    """Extract intent and structured fields from free-form user text."""
    raw = (text or "").strip()
    fields: Dict[str, str] = {}

    if force_intent in ("search", "generate"):
        intent = force_intent
    else:
        intent = "generate" if detect_generate_intent(raw) else "search"

    # Explicit key=value pairs first
    for m in _KV.finditer(raw):
        key = m.group(1).lower()
        val = _clean_capture(m.group(2))
        if key and val:
            fields[key] = val

    m = _CASE_NO.search(raw)
    if m:
        _set(fields, "case_number", m.group(1))
    m = _DEFENDANT.search(raw)
    if m:
        _set(fields, "defendant_name", m.group(1))
        _set(fields, "defendant", m.group(1))
    m = _PLAINTIFF.search(raw)
    if m:
        _set(fields, "plaintiff", m.group(1))
    m = _COUNTY.search(raw)
    if m:
        _set(fields, "county", m.group(1))
    m = _CIRCUIT.search(raw)
    if m:
        circ = m.group(1).upper()
        # normalize "9th" -> keep; word form stay upper
        _set(fields, "judicial_circuit", circ)
    m = _JUDGE.search(raw)
    if m:
        _set(fields, "judge", "Hon. " + _clean_capture(m.group(1)) if not m.group(1).lower().startswith("hon") else m.group(1))
    m = _COUNSEL.search(raw)
    if m:
        _set(fields, "counsel_name", m.group(1))
    m = _BAR.search(raw)
    if m:
        _set(fields, "counsel_bar", m.group(1))
    m = _FIRM.search(raw)
    if m:
        _set(fields, "counsel_firm", m.group(1))
    m = _PHONE.search(raw)
    if m:
        _set(fields, "counsel_phone", m.group(1))
    m = _EMAIL.search(raw)
    if m:
        _set(fields, "counsel_email", m.group(1))
    m = _TRIAL.search(raw)
    if m:
        _set(fields, "current_trial_date", m.group(1))
        _set(fields, "hearing_date", m.group(1))
    m = _CHARGING.search(raw)
    if m:
        _set(fields, "charging_date", m.group(1))
    m = _OFFENSE.search(raw)
    if m:
        _set(fields, "charged_offense", m.group(1))
    m = _EYEWITNESS.search(raw)
    if m:
        _set(fields, "eyewitness_name", m.group(1))
    m = _OFFICER.search(raw)
    if m:
        _set(fields, "officer_name", m.group(1))

    if re.search(r"\bflorida\b|\bfl\b", raw, re.I):
        _set(fields, "state", "Florida")
    if re.search(r"\bcircuit\b", raw, re.I):
        _set(fields, "court_level", "CIRCUIT")
    if re.search(r"\bcriminal\b", raw, re.I):
        _set(fields, "court_division", "Criminal")
    if re.search(r"\bcivil\b", raw, re.I):
        _set(fields, "court_division", "Civil")

    # Search text: drop pure generate verbs so template matching stays clean
    search_text = _STRIP_GENERATE.sub(" ", raw)
    search_text = re.sub(r"\s+", " ", search_text).strip(" ,.;")

    # Narrative leftovers: store full prompt for facts if long enough
    narrative = raw
    if len(raw) > 40:
        fields.setdefault("factual_background", raw)
        fields.setdefault("additional_grounds", raw)

    return ParsedQuery(
        raw=raw,
        intent=intent,
        search_text=search_text or raw,
        fields=fields,
        narrative=narrative,
    )


def parsed_to_form_defaults(parsed: ParsedQuery, *, template_name: str = "") -> Dict[str, Any]:
    """Flatten ParsedQuery into generate-form defaults."""
    f = dict(parsed.fields)
    defendant = f.get("defendant_name") or f.get("defendant") or ""
    defaults: Dict[str, Any] = {
        "motion_title": f.get("motion_title") or template_name or "Motion",
        "case_number": f.get("case_number", ""),
        "court_name": f.get("court_name", ""),
        "court_division": f.get("court_division", "Criminal"),
        "county": f.get("county", ""),
        "state": f.get("state", "Florida"),
        "court_level": f.get("court_level", "CIRCUIT"),
        "judicial_circuit": f.get("judicial_circuit", ""),
        "plaintiff": f.get("plaintiff", "State of Florida"),
        "defendant_name": defendant,
        "judge": f.get("judge", ""),
        "filing_date": f.get("filing_date", date.today().strftime("%B %d, %Y")),
        "counsel_name": f.get("counsel_name", ""),
        "counsel_bar": f.get("counsel_bar", ""),
        "counsel_firm": f.get("counsel_firm", ""),
        "counsel_phone": f.get("counsel_phone", ""),
        "counsel_email": f.get("counsel_email", ""),
        "counsel_address": f.get("counsel_address", ""),
        "charging_date": f.get("charging_date", ""),
        "current_trial_date": f.get("current_trial_date", ""),
        "requested_continuance_date": f.get("requested_continuance_date", ""),
        "service_date": f.get("service_date", f.get("filing_date", date.today().strftime("%B %d, %Y"))),
        "eyewitness_name": f.get("eyewitness_name", ""),
        "officer_name": f.get("officer_name", ""),
        "identification_date": f.get("identification_date", ""),
        "identification_place": f.get("identification_place", ""),
        "charged_offense": f.get("charged_offense", ""),
        "suggestive_procedure": f.get("suggestive_procedure", ""),
        "additional_grounds": f.get("additional_grounds", ""),
        "factual_background": f.get("factual_background", parsed.narrative if len(parsed.narrative) > 40 else ""),
        "legal_argument": f.get("legal_argument", ""),
        "suppression_relief": f.get("suppression_relief", ""),
        "prayer_for_relief": f.get("prayer_for_relief", ""),
        "certificate_of_service": f.get("certificate_of_service", ""),
        "relief_sought": f.get("relief_sought", ""),
        "hearing_date": f.get("hearing_date", ""),
        "hearing_time": f.get("hearing_time", ""),
        "hearing_location": f.get("hearing_location", ""),
        "movant_name": f.get("movant_name") or defendant,
        "movant_role": f.get("movant_role", "Defendant"),
    }

    # Court name default for FL circuit
    if not defaults["court_name"] and defaults["judicial_circuit"]:
        defaults["court_name"] = (
            f"IN THE CIRCUIT COURT OF THE {defaults['judicial_circuit']} JUDICIAL CIRCUIT"
        )

    # Custom YAML for leftover keys not in the form
    known = set(defaults.keys()) | {"defendant", "template_id", "motion_title"}
    extra = {k: v for k, v in f.items() if k not in known and v}
    if extra:
        import yaml

        defaults["custom_yaml"] = yaml.safe_dump(extra, sort_keys=False).strip()

    return {k: v for k, v in defaults.items() if v is not None}
