"""Search motion templates by free-text description."""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from motion_bot.catalog import TemplateEntry, list_templates

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Too generic to count as a real match by themselves
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "case",
    "court",
    "create",
    "draft",
    "file",
    "fl",
    "florida",
    "for",
    "form",
    "from",
    "generate",
    "give",
    "i",
    "in",
    "is",
    "it",
    "library",
    "make",
    "me",
    "motion",
    "motions",
    "my",
    "need",
    "of",
    "on",
    "or",
    "please",
    "prepare",
    "request",
    "template",
    "templates",
    "the",
    "this",
    "to",
    "want",
    "with",
    "write",
}

# Lightweight synonyms so natural descriptions match catalog wording
_SYNONYMS = {
    "continue": {"continuance", "continue", "postpone", "delay", "adjourn"},
    "continuance": {"continuance", "continue", "postpone", "adjourn"},
    "postpone": {"continuance", "postpone", "adjourn"},
    "adjourn": {"continuance", "adjourn", "postpone"},
    "suppress": {"suppress", "suppression", "exclude", "exclusion"},
    "suppression": {"suppress", "suppression", "exclude"},
    "suppressing": {"suppress", "suppression", "exclude"},
    "eyewitness": {"eyewitness", "witness", "identification", "lineup"},
    "witness": {"eyewitness", "witness", "identification"},
    "identification": {"identification", "eyewitness", "lineup", "photo", "suggestive"},
    "lineup": {"lineup", "identification", "photo"},
    "suggestive": {"suggestive", "suggestiveness", "photo", "mug"},
    "compel": {"compel", "discovery", "interrogatories", "production"},
    "discovery": {"discovery", "compel", "interrogatories", "deposition"},
    "dismiss": {"dismiss", "dismissal"},
    "dismissal": {"dismiss", "dismissal"},
    "jury": {"jury", "instruction"},
    "instruction": {"jury", "instruction"},
    "summary": {"summary", "judgment", "msj"},
    "judgment": {"summary", "judgment", "judgement", "msj"},
    "judgement": {"summary", "judgment", "judgement", "msj"},
    "msj": {"summary", "judgment", "msj"},
}

# Multi-word motion types that should match as a unit when possible
_PHRASES = (
    "summary judgment",
    "summary judgement",
    "motion for continuance",
    "motion to compel",
    "motion to dismiss",
    "motion to suppress",
    "right to counsel",
    "suggestive identification",
    "eyewitness identification",
    "jury instruction",
)

# Minimum score after filtering — blocks weak false positives
_MIN_SCORE = 3.0


def _tokens(text: str) -> Set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _content_tokens(text: str) -> Set[str]:
    return {t for t in _tokens(text) if t not in _STOPWORDS and len(t) > 1}


def _expand(tokens: Set[str]) -> Set[str]:
    expanded = set(tokens)
    for tok in tokens:
        expanded |= _SYNONYMS.get(tok, set())
    return expanded


def _entry_focus_text(entry: TemplateEntry) -> str:
    """Name / type / description only — not every placeholder key."""
    return " ".join(
        [
            entry.id.replace("-", " "),
            entry.name,
            entry.description,
            entry.motion_type.replace("-", " "),
            entry.jurisdiction,
        ]
    )


def _phrase_hits(query: str, blob: str) -> List[str]:
    q = (query or "").lower()
    b = (blob or "").lower()
    hits = []
    for phrase in _PHRASES:
        if phrase in q and phrase in b:
            hits.append(phrase)
        # Query contains phrase that is clearly the motion type sought,
        # even if only part of phrase is in blob we handle via tokens
    return hits


def search_templates(query: str, *, limit: int = 20) -> List[Tuple[TemplateEntry, float]]:
    """Rank templates by relevance; return empty when nothing is a real match."""
    q = (query or "").strip()
    if not q:
        return []

    q_content = _content_tokens(q)
    q_expanded = _expand(q_content)
    if not q_content and not any(p in q.lower() for p in _PHRASES):
        # Only stopwords like "motion for" — not enough to pick a template
        return []

    scored: List[Tuple[TemplateEntry, float]] = []
    q_lower = q.lower()

    for entry in list_templates():
        focus = _entry_focus_text(entry)
        e_content = _content_tokens(focus)
        e_expanded = _expand(e_content)

        # Meaningful overlap only (after stopword removal + synonym expand)
        overlap = q_expanded & e_expanded
        phrases = _phrase_hits(q, focus)

        # No real topical overlap → not a match (e.g. "summary judgment" ≠ continuance)
        if q_content and not overlap and not phrases:
            continue

        # If most distinctive query tokens miss the entry, don't force a match
        if q_content:
            hit_ratio = len(q_expanded & e_expanded) / max(len(q_expanded), 1)
            if hit_ratio < 0.34 and not phrases:
                # Single strong token like "continuance" is enough
                if not (len(q_content) == 1 and (q_content & e_expanded)):
                    continue

        score = 0.0
        score += 2.0 * len(overlap)
        # Prefer hits on title / motion_type
        name_tokens = _expand(_content_tokens(entry.name + " " + entry.motion_type))
        score += 2.5 * len(q_expanded & name_tokens)
        score += 4.0 * len(phrases)

        # If the user named a specific motion family, only keep true family hits
        for phrase in _PHRASES:
            if phrase in q_lower:
                ptoks = _expand(_content_tokens(phrase))
                if ptoks & e_expanded:
                    score += 3.0
                else:
                    score -= 10.0

        if entry.jurisdiction and entry.jurisdiction.lower() in q_lower:
            score += 0.5

        if score < _MIN_SCORE:
            continue

        scored.append((entry, score))

    scored.sort(key=lambda item: (-item[1], item[0].name.lower()))
    return scored[:limit]
