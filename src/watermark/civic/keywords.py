"""BOSC corridor topic/subject vocabulary for scanning meeting text.

Mirrors the commissioners minutes ref-extraction (``subject_*`` / ``topic_*`` hits)
so a subdivision meeting only reaches the corridor timeline when its text actually
touches the data-center thread — not every township meeting. ``scan_text`` is the
one entry point; add a term here, not in the indexer.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable

# Pieces of the `tax_abatement` pattern — the one term whose senses are distinguished by context
# rather than by wording, and the one worth measuring instead of guessing at.
#
# Measured over every `abatement` mention in every committed meetings tree (97 of them): 2 are
# asbestos abatement, 3 lead abatement, 3 nuisance/mowing, 3 "abatement fees" cost recovery — and
# the remaining 86 are tax abatements. Every one of the 8 non-tax mentions QUALIFIES the word
# locally ("asbestos abatement", "lead abatement", "abatement mowing", "abatement fees"), while
# the tax sense routinely does not: Perry Township's entire 2024 data-center abatement debate
# ("WHEN OUR PRESENT ABATEMENTS EXPIRE", "THE SCHOOL AND THE TOWNSHIP WON'T SEE ANY MONEY",
# "ABATEMENTS ARE COMPETITIVE WITH OTHER AREAS") says `tax` in not one of its sixteen sentences.
#
# So name the other senses and let the rest be the tax one. Requiring the tax word instead — the
# #1839 correction — dropped that whole debate, including the 2024-09-05 public hearing where a
# resident testified their "LAND TAXES ARE INCREASING TO PAY FOR THE ABATEMENT THAT WAS GIVEN TO
# THE DATA CENTERS". Re-measure before widening either list; the classes are local vocabulary,
# not universal truth.
_NOT_TAX_BEFORE = (
    r"(?<!asbestos )(?<!asbestos-)(?<!lead )(?<!lead-)"
    r"(?<!nuisance )(?<!weed )(?<!grass )(?<!vegetation )"
)
_NOT_TAX_AFTER = r"(?!\s+(?:fee|fees|mowing|propert|invoice))"
_ABATEMENT = rf"\b{_NOT_TAX_BEFORE}abatements?\b{_NOT_TAX_AFTER}"

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
    # `megawatt hub` alone is a unit + a noun, not a name ("a 150 megawatt hub project"), so the
    # facility alternative carries its town: the disclosed name is the "Findlay Megawatt Hub".
    "one_power": r"one\s+power\s+(?:co\b|company)|findlay\s+megawatt\s+hub|\bmwhub\b",
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
    # See _ABATEMENT above — the exclusions are measured, not assumed.
    "tax_abatement": rf"{_ABATEMENT}|\bcra\b|\btif\b|enterprise\s+zone",
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
