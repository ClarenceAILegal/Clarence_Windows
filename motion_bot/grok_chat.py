"""Grok (xAI) chat engine for Clarence conversational replies."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from motion_bot.catalog import TemplateEntry
from motion_bot.settings import get_xai_api_key


DEFAULT_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
XAI_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")


@dataclass
class GrokChatResult:
    message: str
    offer_generate: bool = False
    offer_form: bool = False
    offer_upload: bool = False
    best_template_id: str = ""
    best_template_name: str = ""
    source: str = "rules"  # "grok" | "rules"


def grok_available() -> bool:
    """True only when *this user/machine* has saved their own API key."""
    return bool(get_xai_api_key())


def _client():
    from openai import OpenAI

    key = get_xai_api_key()
    if not key:
        raise RuntimeError(
            "No Grok API key on this computer. Add your own key in the Clarence menu."
        )
    return OpenAI(api_key=key, base_url=XAI_BASE_URL)


def _catalog_summary(matches: List[tuple], limit: int = 8) -> str:
    if not matches:
        return "(no matching templates in library)"
    lines = []
    for entry, score in matches[:limit]:
        lines.append(
            f"- id={entry.id} | name={entry.name} | type={entry.motion_type or '-'} "
            f"| jurisdiction={entry.jurisdiction or '-'} | score={score:.1f}"
        )
    return "\n".join(lines)


def _system_prompt() -> str:
    return (
        "You are Clarence, a private legal motion assistant for a desktop app. "
        "You help lawyers find motion templates in a local library and generate Word motions. "
        "Be concise, professional, and clear.\n\n"
        "Rules:\n"
        "1) If the library has a good match for the user's request, ask whether they want to:\n"
        "   - generate the motion now (one-shot), or\n"
        "   - fill out the form step by step.\n"
        "2) If there is NO good match, do NOT invent a template. Explicitly ask if they want to "
        "upload a .docx template (drag onto the search bar). Do not offer generate/form as primary options.\n"
        "3) Never recommend a wrong motion type (e.g. continuance when they asked for summary judgment).\n"
        "4) Keep replies short (2–5 sentences) plus the choice guidance.\n"
        "5) Respond with JSON only, no markdown fences, shape:\n"
        "{\n"
        '  "message": "string shown to user",\n'
        '  "offer_generate": true/false,\n'
        '  "offer_form": true/false,\n'
        '  "offer_upload": true/false,\n'
        '  "best_template_id": "id or empty",\n'
        '  "best_template_name": "name or empty"\n'
        "}"
    )


def _user_payload(
    user_text: str,
    matches: List[tuple],
    extracted: Optional[Dict[str, str]] = None,
) -> str:
    return (
        f"User request:\n{user_text}\n\n"
        f"Library matches:\n{_catalog_summary(matches)}\n\n"
        f"Extracted fields (heuristic):\n{json.dumps(extracted or {}, ensure_ascii=False)}\n\n"
        "Decide whether matches are truly relevant. If the best match is wrong motion type, "
        "treat as no match and set offer_upload=true."
    )


def _parse_json_content(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    # Strip optional markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback: treat whole string as message
    return {
        "message": content.strip() or "How would you like to proceed?",
        "offer_generate": False,
        "offer_form": False,
        "offer_upload": True,
        "best_template_id": "",
        "best_template_name": "",
    }


def chat_with_grok(
    user_text: str,
    matches: List[tuple],
    extracted: Optional[Dict[str, str]] = None,
    *,
    model: Optional[str] = None,
) -> GrokChatResult:
    """Call Grok to produce Clarence's chat reply + UI action flags."""
    client = _client()
    model_name = model or DEFAULT_MODEL

    # Prefer chat.completions for broad OpenAI-compat; fall back to responses if needed
    try:
        resp = client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_payload(user_text, matches, extracted)},
            ],
        )
        content = resp.choices[0].message.content or ""
    except Exception:
        # Newer Responses API shape
        resp = client.responses.create(
            model=model_name,
            input=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_payload(user_text, matches, extracted)},
            ],
        )
        content = getattr(resp, "output_text", None) or ""

    data = _parse_json_content(content)
    best_id = str(data.get("best_template_id") or "")
    best_name = str(data.get("best_template_name") or "")
    if not best_id and matches:
        # Only auto-fill best match if Grok offered generate/form
        if data.get("offer_generate") or data.get("offer_form"):
            best_id = matches[0][0].id
            best_name = matches[0][0].name

    return GrokChatResult(
        message=str(data.get("message") or "").strip()
        or "How would you like to proceed?",
        offer_generate=bool(data.get("offer_generate")),
        offer_form=bool(data.get("offer_form")),
        offer_upload=bool(data.get("offer_upload")),
        best_template_id=best_id,
        best_template_name=best_name,
        source="grok",
    )


def rules_chat(
    user_text: str,
    matches: List[tuple],
    extracted: Optional[Dict[str, str]] = None,
) -> GrokChatResult:
    """Deterministic fallback when no API key / Grok unavailable."""
    if not matches:
        return GrokChatResult(
            message=(
                f'I don’t have a matching motion template in your library for “{user_text.strip()}”.\n\n'
                "Would you like to upload a template? Drop a Word document (.docx) onto the bar below "
                "and I’ll add it to your library automatically. Then send your request again."
            ),
            offer_generate=False,
            offer_form=False,
            offer_upload=True,
            source="rules",
        )

    best: TemplateEntry = matches[0][0]
    count = len(matches)
    if count == 1:
        found = f'a matching motion in your library (**{best.name}**)'
    else:
        found = f"{count} possible matches (top: **{best.name}**)"

    return GrokChatResult(
        message=(
            f"Got it. I found {found}. How would you like to proceed?\n\n"
            "• Generate the motion for me (one-shot), or\n"
            "• Fill out the form step by step"
        ),
        offer_generate=True,
        offer_form=True,
        offer_upload=False,
        best_template_id=best.id,
        best_template_name=best.name,
        source="rules",
    )


def clarence_reply(
    user_text: str,
    matches: List[tuple],
    extracted: Optional[Dict[str, str]] = None,
    *,
    use_grok: bool = False,
) -> GrokChatResult:
    """Chat reply. Grok is opt-in via use_grok (never used for generate/form fill).

    One-shot generation and form pathways do not call this with use_grok=True
    for document creation — only the conversational chat step may bill.
    """
    if not use_grok or not grok_available():
        result = rules_chat(user_text, matches, extracted)
        if use_grok and not grok_available():
            result.message = (
                "Grok is on, but this computer has no API key — using free built-in chat. "
                "Add your own key under the bear menu (each user needs their own).\n\n"
                + result.message
            )
        return result
    try:
        return chat_with_grok(user_text, matches, extracted)
    except Exception as exc:  # noqa: BLE001
        fallback = rules_chat(user_text, matches, extracted)
        fallback.message = (
            f"(Grok unavailable — free mode used: {exc})\n\n" + fallback.message
        )
        fallback.source = "rules"
        return fallback
