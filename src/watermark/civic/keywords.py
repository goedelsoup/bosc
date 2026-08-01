"""BOSC corridor topic/subject vocabulary for scanning meeting text.

Mirrors the commissioners minutes ref-extraction (``subject_*`` / ``topic_*`` hits)
so a subdivision meeting only reaches the corridor timeline when its text actually
touches the data-center thread — not every township meeting. ``scan_text`` is the
one entry point; add a term here, not in the indexer.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable

# slug -> case-insensitive pattern. Subjects (named parties) + topics (corridor acts).
_TERMS: dict[str, str] = {
    # subjects
    "bosc": r"\bbosc\b|project\s+bosc",
    "bistrozzi": r"bistrozzi",
    "hume": r"\bhume\b",
    "google": r"\bgoogle\b",
    "amazon": r"\bamazon\b",
    "general_dynamics": r"general\s+dynamics",
    # Findlay's own disclosed parties (#1839). Both patterns are deliberately narrower than the
    # bare company name, because Findlay is the town where the ambiguity bites:
    # ``\bmara\b`` alone would be a coin-flip against a surname, and MARA Holdings is NOT
    # Marathon Petroleum (headquartered in Findlay) — see data/extracted/findlay/data-centers.md,
    # which makes that guard explicit. So each requires the full name or the facility's own name.
    "one_power": r"one\s+power\s+(?:co\b|company)|megawatt\s+hub|\bmwhub\b",
    "mara_holdings": r"mara\s+holdings|marathon\s+digital",
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


# The project-specific subjects that make a meeting corridor-relevant (timeline/summary-worthy)
# are **per-site**, not a module constant: they live on ``SiteProfile.corridor_subjects``
# (``bosc``/``bistrozzi``/``datacenter``/``google`` for Lima; empty for a peer until it declares
# its own) — the single source of truth (#1523). This predicate takes that vocabulary as an
# argument so the module stays pure (no config/sites import); callers read
# ``active_profile(settings).corridor_subjects`` and pass it in. Generic township topics
# (rezoning/easement/...) and ambiguous names (``hume``/``amazon``) stay in ``scan_text``'s
# vocabulary — searchable index ``hits`` — but never appear in ``subjects``.


def is_corridor_relevant(hits: Iterable[str], subjects: Collection[str]) -> bool:
    """True if ``hits`` names one of the active site's corridor ``subjects``.

    ``subjects`` is the active site's ``SiteProfile.corridor_subjects``; empty when a site
    declares none, so nothing is corridor-relevant there (the safe/honest default).
    """
    return any(h in subjects for h in hits)
