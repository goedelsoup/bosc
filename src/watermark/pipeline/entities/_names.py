"""Party name normalization + classification — the leaf toolkit of the entity graph.

Split out of the former monolithic ``entities.py`` (#598). Pure string/regex work with no
``EntityGraph`` dependency: normalize a raw party string to a canonical key, classify it
(government / corporate / individual / trust / facility / water), and split principals /
trustee recitals. Re-exported from :mod:`watermark.pipeline.entities`.
"""

from __future__ import annotations

import re
from typing import Literal, get_args

_LEGAL_SUFFIXES = frozenset(
    {
        "LLC",
        "LLP",
        "LP",
        "INC",
        "CORP",
        "CORPORATION",
        "CO",
        "COMPANY",
        "LTD",
        "LIMITED",
        "LIABILITY",
        "PLLC",
        "TRUST",
    }
)
_CORPORATE_TOKENS = frozenset(
    {"LLC", "LLP", "LP", "INC", "CORP", "CORPORATION", "COMPANY", "LTD", "PLLC"}
)
# Phrases that mark a government / public body (matched on the raw upper string).
_GOV_PHRASES = (
    "PORT AUTHORITY",
    "BOARD OF COMMISSIONERS",
    "COMMISSIONERS",
    "STATE OF OHIO",
    "CITY OF",
    "VILLAGE OF",
    "SANITARY ENGINEER",
    "BOARD OF EDUCATION",
    "BOARD OF TOWNSHIP",
    "COUNTY ENGINEER",
    "LAND BANK",
    "HOUSING AUTHORITY",
    "PLANNING COMMISSION",  # regional/metropolitan planning commissions (e.g. Miami Valley RPC)
)
# Federal military departments / defense agencies — a government body, but ``government_military``
# not ``government_local`` (checked before ``_GOV_PHRASES``). Kept specific so it never catches a
# corporate "Air Force Federal Credit Union"-style name (#1660: the WPAFB CERCLA FFA names the
# "United States Department of the Air Force", which was mis-classified as ``individual``).
_MILITARY_GOV_PHRASES = (
    "DEPARTMENT OF THE AIR FORCE",
    "DEPARTMENT OF THE ARMY",
    "DEPARTMENT OF THE NAVY",
    "DEPARTMENT OF DEFENSE",
    "DEFENSE LOGISTICS AGENCY",
    "ARMY CORPS OF ENGINEERS",
)
# Out-of-state incorporation hints — a shell-adjacent *signal*, never a verdict.
_FOREIGN_HINTS = ("DELAWARE", "WYOMING", "NEVADA")
_FACILITY_HINTS = ("WWTP", "TREATMENT PLANT", "TREATMENT WORKS", "WASTEWATER")
_WATER_HINTS = ("RUN", "RIVER", "CREEK", "DITCH", "DRAIN", "LAKE")


def _base_permit(permit_no: str) -> str:
    """Strip the ``*LD`` / ``*MD`` action suffix to a stable facility id."""
    return permit_no.split("*", 1)[0].strip()


def _looks_like_person(s: str) -> bool:
    """Heuristic: 2-4 capitalized name tokens, no corporate/government markers.

    "Randy Barrera", "Scott J. Ziance" -> True; "Bistrozzi LLC", "NEFF FARMS",
    "Allen County Board of Commissioners" -> False.
    """
    s = s.strip()
    if not s:
        return False
    up = s.upper()
    if any(re.search(rf"\b{re.escape(t)}\b", up) for t in _CORPORATE_TOKENS):
        return False
    if "COUNTY" in up or "TRUST" in up or " AND " in f" {up} ":
        return False
    tokens = s.split()
    if not 2 <= len(tokens) <= 4:
        return False
    # Each token is an initial ("J.") or a Capitalized word with a lowercase tail
    # ("Randy") — ALL-CAPS tokens ("NEFF", "FARMS") are rejected as org-like.
    return all(re.fullmatch(r"[A-Z]\.?|[A-Z][a-z][a-zA-Z.'-]*", t) for t in tokens)


def _split_principal(raw: str) -> tuple[str, str | None]:
    """Split a "Person, Org LLC" applicant into ``(org, person)``.

    The model sometimes records an applicant as "Randy Barrera, Tilted Gate LLC".
    Resolve the org as the primary entity and the person as its principal. Returns
    ``(raw, None)`` when the string isn't that pattern (e.g. "Bistrozzi LLC, a
    Delaware limited liability company" — the part before the comma isn't a
    person, so it is left intact).
    """
    if "," not in raw:
        return raw, None
    before, after = (p.strip() for p in raw.split(",", 1))
    after_is_org = bool(
        re.search(r"\b(?:LLC|LLP|LP|INC|CORP|CORPORATION|COMPANY|LTD|PLLC)\b", after.upper())
    )
    if (
        _looks_like_person(before)
        and after_is_org
        and not after.lower().startswith(("a ", "an ", "the "))
    ):
        return after, before
    return raw, None


def _split_multi(raw: str) -> list[str]:
    """Split a field that the model packed with multiple values into parts.

    Splits only on ``;`` and newlines — *not* commas, because a firm name carries
    internal commas ("Vorys, Sater, Seymour, and Pease"). ``"Heather Dardinger;
    Scott J. Ziance"`` -> two names.
    """
    return [p.strip() for p in re.split(r"[;\n]", raw) if p.strip()]


# One or more persons acting as trustee(s) of a named trust, e.g. "Kyle C. Brenneman
# and Sarah N. Brenneman, Co-Trustees of the Kyle C. Brenneman Living Trust dated March
# 30, 2023, and any amendments thereto". The ``,?`` eats the comma before the role word.
_TRUSTEE_RE = re.compile(
    r"^(?P<persons>.+?),?\s+(?:as\s+)?(?:co-?\s*)?trustees?\s+(?:of|for|under)\s+(?P<trust>.+)$",
    re.IGNORECASE,
)


def _clean_trust_name(raw: str) -> str:
    """Strip a trust recital to its bare name.

    Drops a leading "the" and the trailing "dated <date> ... and any amendments thereto"
    boilerplate so the trust resolves to a stable node: "the Kyle C. Brenneman Living
    Trust dated March 30, 2023, and any amendments thereto" -> "Kyle C. Brenneman Living
    Trust".
    """
    s = re.sub(r"^the\s+", "", raw.strip(), flags=re.IGNORECASE)
    s = re.split(r"\s+dated\b", s, maxsplit=1, flags=re.IGNORECASE)[0]
    s = re.split(r",?\s+and any amendments\b", s, maxsplit=1, flags=re.IGNORECASE)[0]
    return s.strip().rstrip(",").strip()


def _parse_trustee_recital(raw: str) -> tuple[str, list[str]] | None:
    """Split "X [and Y], (Co-)Trustee(s) of the Z Trust ..." into ``(trust, trustees)``.

    Returns ``None`` when the string isn't a trustee recital — no "trustee of" clause, the
    named instrument isn't a trust, or the actors don't look like persons — so a plain
    person/org is left untouched (omission over a fabricated split).
    """
    m = _TRUSTEE_RE.match(raw.strip())
    if m is None:
        return None
    trust = _clean_trust_name(m.group("trust"))
    if "trust" not in trust.lower():
        return None  # "Trustee of the X Foundation/Estate" — not a trust; don't guess
    persons = [
        p.strip() for p in re.split(r"\s*(?:,|&|\band\b)\s*", m.group("persons")) if p.strip()
    ]
    persons = [p for p in persons if _looks_like_person(p)]
    if not persons:
        return None
    return trust, persons


def normalize_name(raw: str) -> str:
    """Canonical key: uppercased, descriptive clause and legal suffixes removed.

    ``"Bistrozzi LLC, a Delaware Limited Liability Company"`` and ``"BISTROZZI
    LLC"`` both reduce to ``"BISTROZZI"``; ``"Scott J. Ziance"`` and ``"Scott
    Ziance"`` both reduce to ``"SCOTT ZIANCE"`` (interior single-letter initials
    are dropped) so name variants resolve to one entity.
    """
    head = raw.upper().split(",", 1)[0]  # drop the post-comma descriptive clause
    head = re.sub(r"[^\w\s&]", " ", head)
    tokens = head.split()
    while tokens and tokens[0] == "THE":
        tokens.pop(0)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    # Drop interior single-letter initials (a middle initial is matching noise);
    # keep the first and last token so "C T" (CT Corporation) is left intact.
    if len(tokens) > 2:
        tokens = [tokens[0], *[t for t in tokens[1:-1] if len(t) > 1], tokens[-1]]
    return " ".join(tokens)


def classify(raw: str) -> tuple[str, str, tuple[str, ...]]:
    """Return ``(kind, classification, signals)`` for a party name.

    Conservative: a name is only ``corporate_out_of_state`` (not "shell") when an
    out-of-state hint is present, and that hint is also surfaced as a signal.
    """
    up = raw.upper()
    signals = tuple(h.lower() for h in _FOREIGN_HINTS if h in up)

    if any(h in up for h in _FACILITY_HINTS):
        return "facility", "facility", signals
    if any(p in up for p in _MILITARY_GOV_PHRASES):
        return "government", "government_military", signals
    is_county_body = bool(re.search(r"\bCOUNTY\b", up)) and "FARM" not in up
    if any(p in up for p in _GOV_PHRASES) or is_county_body:
        return "government", "government_local", signals
    if "TRUST" in up or "TRUSTEE" in up:
        return "trust", "trust", signals
    if any(re.search(rf"\b{re.escape(t)}\b", up) for t in _CORPORATE_TOKENS):
        klass = "corporate_out_of_state" if signals else "corporate_domestic"
        return "corporate", klass, signals
    if any(re.search(rf"\b{h}\b", up) for h in _WATER_HINTS):
        return "water", "receiving_water", signals
    return "individual", "individual", signals


# How a corpus-verified party relates to Project BOSC — an editorial classification
# layered onto the graph (see enrich_with_relation_classes). Ordered by proximity to
# the project for grouped rendering. This is a reading of an ALREADY-verified party,
# never a license to add one (Google stays an annotation, off-graph).
RelationClass = Literal[
    "bosc_relation",  # Project BOSC itself / its campus facilities
    "direct_approval",  # a body that voted/permitted the project
    "direct_manage",  # operates/builds the campus or its forcemains/sewer linkage
    "direct_beneficiary",  # named recipient of the public benefit (abatement, revenue)
    "possible_end_user",  # demand-fit only; connection unestablished (rare on-graph)
    "environmental_beneficiary",  # a receiving water / body bearing the externality
    "govt_relation",  # known tie to another government entity
]
RELATION_CLASS_ORDER: tuple[str, ...] = get_args(RelationClass)
