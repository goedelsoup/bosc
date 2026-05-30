"""Format profiles for cost-estimate extraction.

A :class:`Profile` captures everything contractor/format-specific that the
extractor needs: the section vocabulary to expect, the markup convention, item-
numbering scheme, layout cues, and keywords for auto-detection. The generic
:class:`bosc.models.Estimate` stays format-agnostic; profiles supply the prompt
knowledge and a soft expectation to reconcile against.

Add a new contractor by registering another ``Profile`` — no model changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from bosc.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class MarkupConvention:
    """An expected markup line for a format (e.g. contingency at 25%)."""

    label: str
    rate: float | None = None  # fraction of the construction subtotal, if a %


@dataclass(frozen=True)
class Profile:
    """A contractor/agency cost-estimate format."""

    id: str
    display_name: str
    kind: str = "opc"
    document_title: str = "Opinion of Probable Cost"
    expected_sections: tuple[str, ...] = ()  # vocabulary hint, NOT enforced
    markups: tuple[MarkupConvention, ...] = ()
    item_number_scheme: str = ""
    layout_notes: str = ""
    detect_keywords: tuple[str, ...] = ()  # lowercased substrings scored against OCR text

    # -- detection ----------------------------------------------------------
    def detect_score(self, text: str) -> int:
        """How many detection keywords appear in ``text`` (lowercased)."""
        low = text.lower()
        return sum(1 for kw in self.detect_keywords if kw in low)

    # -- prompt -------------------------------------------------------------
    def _markup_hint(self) -> str:
        if not self.markups:
            return "any markup/adjustment lines below the construction subtotal"
        parts = [
            f"{m.label}" + (f" (~{m.rate:.0%} of the construction subtotal)" if m.rate else "")
            for m in self.markups
        ]
        return "; ".join(parts)

    def prompt(self, *, detail: bool) -> str:
        """Build the extraction instructions for this format."""
        sections = (
            f"Sections seen on this format include: {', '.join(self.expected_sections)}. "
            "Record sections AS PRINTED on the sheet — do not force them into this list; "
            "capture whatever sections actually appear."
            if self.expected_sections
            else "Record each section AS PRINTED on the sheet."
        )
        line_item_rule = (
            (
                "  * For each section, extract EVERY line item: item_no "
                f"({self.item_number_scheme or 'item code or a custom_* tag'}), description, "
                "quantity, unit, unit_amount (per-unit $), total_amount (extended $).\n"
                "  * For a lump-sum (LS) item: quantity = 1 and unit_amount = total_amount.\n"
                "  * If a quantity/rate was inferred from the total, add a note saying so.\n"
            )
            if detail
            else "  * Record each section's name and SUBTOTAL (no line items needed).\n"
        )
        return (
            f'You are reading ONE page of a {self.display_name} "{self.document_title}" '
            "cost estimate. Read figures from the IMAGE, which is authoritative. An OCR text "
            "layer may be provided as a hint, but its digits are frequently wrong — never trust "
            "a number from it; read every figure off the image.\n\n"
            "Record into the tool a generic estimate:\n"
            "  * name: the estimate / project title printed on the sheet.\n"
            f"  * sections: {sections}\n"
            f"{line_item_rule}"
            f"  * markups: each adjustment below the construction subtotal — {self._markup_hint()} "
            "— with its label, rate (fraction, if a %), and amount.\n"
            "  * construction_subtotal and total.\n\n"
            f"{self.layout_notes}\n\n"
            "Rules:\n"
            "  * Dollar subtotals and totals must be read carefully (high confidence).\n"
            "  * total MUST be populated: construction_subtotal plus the markups.\n"
            "  * If a figure is illegible, give your best read AND add a warning naming it.\n"
            "  * Never invent sections or line items. Prefer omission over fabrication.\n"
            "  * Set confidence (high/medium/low) for the page overall.\n"
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Profile] = {}


def register(profile: Profile) -> Profile:
    _REGISTRY[profile.id] = profile
    return profile


def get(profile_id: str) -> Profile:
    if profile_id not in _REGISTRY:
        raise KeyError(f"unknown profile {profile_id!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[profile_id]


def all_profiles() -> list[Profile]:
    return list(_REGISTRY.values())


def detect(text: str) -> Profile | None:
    """Best-matching profile for a page's OCR text, or None if nothing scores."""
    scored = [(p.detect_score(text), p) for p in _REGISTRY.values() if p.detect_keywords]
    scored = [(s, p) for s, p in scored if s > 0]
    if not scored:
        return None
    scored.sort(key=lambda sp: sp[0], reverse=True)
    return scored[0][1]


def resolve(profile_id: str | None, text: str) -> Profile:
    """Pick a profile: explicit id wins, else auto-detect, else the generic fallback."""
    if profile_id and profile_id != "auto":
        return get(profile_id)
    detected = detect(text)
    if detected is not None:
        log.info("profile.detected", profile=detected.id)
        return detected
    log.info("profile.fallback", profile=GENERIC_OPC.id)
    return GENERIC_OPC


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

GENERIC_OPC = register(
    Profile(
        id="generic",
        display_name="generic contractor",
        document_title="Opinion of Probable Cost",
        layout_notes=(
            "The sheet typically ends with a roll-up block: a construction subtotal, "
            "one or more markup lines (contingency, inflation, etc.), then a grand total."
        ),
    )
)

TETRATECH = register(
    Profile(
        id="tetratech",
        display_name="Tetra Tech",
        document_title="Opinion of Probable Project Cost",
        expected_sections=(
            "ROADWAY",
            "EROSION_CONTROL",
            "DRAINAGE",
            "PAVEMENT",
            "WATER_WORK",
            "LIGHTING",
            "TRAFFIC_CONTROL",
            "LANDSCAPING",
            "RIGHT_OF_WAY",
            "INCIDENTALS",
            "DESIGN_SURVEY_INSPECTION",
        ),
        markups=(MarkupConvention(label="Contingency and Inflation", rate=0.25),),
        item_number_scheme="ODOT item numbers (e.g. 203E10000), or a custom_* tag for non-standard lines",
        layout_notes=(
            "The sheet ENDS with a roll-up block (lower area): CONSTRUCTION SUBTOTAL, then a "
            "CONTINGENCY AND INFLATION (25%) line, then TOTAL. total = construction_subtotal "
            "+ the 25% line (~1.25x the subtotal); if the 25% line is illegible, infer it as "
            "25% of the construction subtotal and warn."
        ),
        detect_keywords=(
            "tetra tech",
            "tetratech",
            "opinion of probable",
            "conceptual opc",
        ),
    )
)
