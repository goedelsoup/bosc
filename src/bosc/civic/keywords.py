"""BOSC corridor topic/subject vocabulary for scanning meeting text.

Mirrors the commissioners minutes ref-extraction (``subject_*`` / ``topic_*`` hits)
so a subdivision meeting only reaches the corridor timeline when its text actually
touches the data-center thread — not every township meeting. ``scan_text`` is the
one entry point; add a term here, not in the indexer.
"""

from __future__ import annotations

import re

# slug -> case-insensitive pattern. Subjects (named parties) + topics (corridor acts).
_TERMS: dict[str, str] = {
    # subjects
    "bosc": r"\bbosc\b|project\s+bosc",
    "bistrozzi": r"bistrozzi",
    "hume": r"\bhume\b",
    "google": r"\bgoogle\b",
    "amazon": r"\bamazon\b",
    "general_dynamics": r"general\s+dynamics",
    # topics
    "datacenter": r"data\s*\-?\s*cent(?:er|re)|hyperscale",
    "pump_station": r"pump\s*station",
    "forcemain": r"force\s*main",
    "cmar": r"\bcmar\b|construction\s+manager\s+at\s+risk",
    "rezoning": r"re\-?zon(?:e|ing)|zoning\s+(?:amend|change|map)",
    "annexation": r"annex(?:ation|ed|ing)?\b",
    "easement": r"easement",
    "pipeline": r"pipe\s*line",
    "bess": r"\bbess\b|battery\s+energy\s+storage",
    "solar": r"\bsolar\b",
    "setback": r"set\s*back",
    "tax_abatement": r"abatement|\bcra\b|\btif\b|enterprise\s+zone",
}
_COMPILED: dict[str, re.Pattern[str]] = {k: re.compile(v, re.IGNORECASE) for k, v in _TERMS.items()}


def scan_text(text: str) -> list[str]:
    """Sorted corridor-topic slugs whose pattern appears in ``text`` (empty if none)."""
    if not text:
        return []
    return sorted(slug for slug, pat in _COMPILED.items() if pat.search(text))
