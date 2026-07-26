"""Search motion templates by free-text description."""

from __future__ import annotations

import re
from typing import List, Tuple

from motion_bot.catalog import TemplateEntry, list_templates

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Lightweight synonyms so natural descriptions match catalog wording
_SYNONYMS = {
    "continue": {"continuance", "continue", "postpone", "delay", "trial"},
    "continuance": {"continuance", "continue", "postpone", "adjourn"},
    "suppress": {"suppress", "suppression", "exclude", "exclusion", "identification"},
    "suppressing": {"suppress", "suppression", "exclude"},
    "eyewitness": {"eyewitness", "witness", "identification", "lineup", "photo"},
    "id": {"identification", "eyewitness", "lineup"},
    "identification": {"identification", "eyewitness", "lineup", "photo", "suggestive"},
    "lineup": {"lineup", "identification", "counsel", "photo"},
    "counsel": {"counsel", "attorney", "lawyer", "right"},
    "suggestive": {"suggestive", "suggestiveness", "photo", "mug", "identification"},
    "compel": {"compel", "discovery", "interrogatories", "production"},
    "discovery": {"discovery", "compel", "interrogatories", "deposition"},
    "dismiss": {"dismiss", "dismissal"},
    "jury": {"jury", "instruction", "eyewitness"},
    "florida": {"florida", "fl"},
    "fl": {"florida", "fl"},
}


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _expand(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for tok in tokens:
        expanded |= _SYNONYMS.get(tok, set())
    return expanded


def _entry_blob(entry: TemplateEntry) -> str:
    return " ".join(
        [
            entry.id,
            entry.name,
            entry.description,
            entry.jurisdiction,
            entry.motion_type,
            entry.notes,
            entry.source,
            " ".join(entry.placeholders),
        ]
    )


def search_templates(query: str, *, limit: int = 20) -> List[Tuple[TemplateEntry, float]]:
    """Rank templates by relevance to a natural-language motion description."""
    q = (query or "").strip()
    if not q:
        return []

    q_tokens = _expand(_tokens(q))
    if not q_tokens:
        return []

    scored: List[Tuple[TemplateEntry, float]] = []
    for entry in list_templates():
        blob = _entry_blob(entry)
        e_tokens = _expand(_tokens(blob))
        overlap = q_tokens & e_tokens
        if not overlap:
            # substring fallback for multi-word phrases in name/description
            low = blob.lower()
            if q.lower() in low:
                score = 2.0
            else:
                continue
        else:
            score = float(len(overlap))
            # Boost direct hits on motion type / name words
            name_tokens = _tokens(entry.name + " " + entry.motion_type)
            score += 1.5 * len(q_tokens & name_tokens)
            if entry.jurisdiction and entry.jurisdiction.lower() in q.lower():
                score += 1.0
        scored.append((entry, score))

    scored.sort(key=lambda item: (-item[1], item[0].name.lower()))
    return scored[:limit]
