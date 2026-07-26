"""Case and motion data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Party:
    name: str
    role: str = ""  # e.g. Plaintiff, Defendant, Movant
    counsel: str = ""
    bar_number: str = ""
    firm: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""

    def to_context(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CaseCaption:
    court_name: str
    court_division: str = ""
    county: str = ""
    state: str = ""
    case_number: str = ""
    judge: str = ""
    plaintiff: str = ""
    defendant: str = ""
    other_parties: list[str] = field(default_factory=list)

    def to_context(self) -> dict[str, Any]:
        data = asdict(self)
        data["other_parties"] = list(self.other_parties)
        return data


@dataclass
class MotionRequest:
    """All fields used to fill a motion template."""

    template_id: str
    motion_title: str
    caption: CaseCaption
    movant: Party
    respondent: Party | None = None
    hearing_date: str = ""
    hearing_time: str = ""
    hearing_location: str = ""
    filing_date: str = field(default_factory=lambda: date.today().isoformat())
    relief_sought: str = ""
    factual_background: str = ""
    legal_argument: str = ""
    prayer_for_relief: str = ""
    certificate_of_service: str = ""
    exhibits: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> dict[str, Any]:
        """Flatten into a Jinja/docxtpl context dict."""
        ctx: dict[str, Any] = {
            "template_id": self.template_id,
            "motion_title": self.motion_title,
            "hearing_date": self.hearing_date,
            "hearing_time": self.hearing_time,
            "hearing_location": self.hearing_location,
            "filing_date": self.filing_date,
            "relief_sought": self.relief_sought,
            "factual_background": self.factual_background,
            "legal_argument": self.legal_argument,
            "prayer_for_relief": self.prayer_for_relief,
            "certificate_of_service": self.certificate_of_service,
            "exhibits": list(self.exhibits),
            "caption": self.caption.to_context(),
            "movant": self.movant.to_context(),
            "respondent": self.respondent.to_context() if self.respondent else {},
        }
        # Common flat aliases for simpler Lexis-style placeholders
        cap = self.caption
        mov = self.movant
        ctx.update(
            {
                "court_name": cap.court_name,
                "court_division": cap.court_division,
                "county": cap.county,
                "state": cap.state,
                "case_number": cap.case_number,
                "judge": cap.judge,
                "plaintiff": cap.plaintiff,
                "defendant": cap.defendant,
                "movant_name": mov.name,
                "movant_role": mov.role,
                "counsel_name": mov.counsel or mov.name,
                "counsel_bar": mov.bar_number,
                "counsel_firm": mov.firm,
                "counsel_address": mov.address,
                "counsel_phone": mov.phone,
                "counsel_email": mov.email,
            }
        )
        if self.respondent:
            ctx["respondent_name"] = self.respondent.name
            ctx["respondent_role"] = self.respondent.role
        ctx.update(self.custom)
        return ctx


def motion_from_dict(data: dict[str, Any]) -> MotionRequest:
    """Build a MotionRequest from JSON/YAML case data."""
    caption_raw = data.get("caption") or {}
    movant_raw = data.get("movant") or {}
    respondent_raw = data.get("respondent")

    caption = CaseCaption(
        court_name=caption_raw.get("court_name", data.get("court_name", "")),
        court_division=caption_raw.get("court_division", ""),
        county=caption_raw.get("county", ""),
        state=caption_raw.get("state", ""),
        case_number=caption_raw.get("case_number", data.get("case_number", "")),
        judge=caption_raw.get("judge", ""),
        plaintiff=caption_raw.get("plaintiff", data.get("plaintiff", "")),
        defendant=caption_raw.get("defendant", data.get("defendant", "")),
        other_parties=list(caption_raw.get("other_parties") or []),
    )
    movant = Party(
        name=movant_raw.get("name", data.get("movant_name", "")),
        role=movant_raw.get("role", "Movant"),
        counsel=movant_raw.get("counsel", ""),
        bar_number=movant_raw.get("bar_number", ""),
        firm=movant_raw.get("firm", ""),
        address=movant_raw.get("address", ""),
        phone=movant_raw.get("phone", ""),
        email=movant_raw.get("email", ""),
    )
    respondent = None
    if respondent_raw:
        respondent = Party(
            name=respondent_raw.get("name", ""),
            role=respondent_raw.get("role", "Respondent"),
            counsel=respondent_raw.get("counsel", ""),
            bar_number=respondent_raw.get("bar_number", ""),
            firm=respondent_raw.get("firm", ""),
            address=respondent_raw.get("address", ""),
            phone=respondent_raw.get("phone", ""),
            email=respondent_raw.get("email", ""),
        )

    return MotionRequest(
        template_id=data["template_id"],
        motion_title=data.get("motion_title", "Motion"),
        caption=caption,
        movant=movant,
        respondent=respondent,
        hearing_date=data.get("hearing_date", ""),
        hearing_time=data.get("hearing_time", ""),
        hearing_location=data.get("hearing_location", ""),
        filing_date=data.get("filing_date", date.today().isoformat()),
        relief_sought=data.get("relief_sought", ""),
        factual_background=data.get("factual_background", ""),
        legal_argument=data.get("legal_argument", ""),
        prayer_for_relief=data.get("prayer_for_relief", ""),
        certificate_of_service=data.get("certificate_of_service", ""),
        exhibits=list(data.get("exhibits") or []),
        custom=dict(data.get("custom") or {}),
    )
