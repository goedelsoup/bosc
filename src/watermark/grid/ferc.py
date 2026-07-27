"""Model the FERC<->PUCO jurisdictional seam for the campus (#97, epic #93).

The regulatory layer that sits between the serving utility (#94) and the federal
energy-policy layer (#98): which government sets the rules for the campus's power. The
Federal Power Act splits authority on a line drawn at the wholesale/retail boundary -
the Federal Energy Regulatory Commission (FERC) governs **wholesale** sales of
electricity, **interstate transmission**, and the RTO market rules (PJM), while the
Public Utilities Commission of Ohio (PUCO) governs Ohio **retail** electric service,
distribution, and retail rates. This module captures, as cited evidence (not asserted):

- the **jurisdictional map** (FERC scope vs PUCO scope, with the statutory anchor in
  Federal Power Act sections 205/206), and where the campus's arrangement falls;
- the active **large-load / co-location dockets** at FERC (real public proceedings on
  data-center co-location at generators in PJM), captured as cited pointers; and
- a **FERC Form 1** pointer for the serving utility / transmission owner financials.

Data discipline (epic #93): the general law is cited at high confidence; specific
dockets and any transcribed Form-1 figure are flagged ``verify`` and held at medium (or
lower) confidence, with a citation to the FERC eLibrary docket number / FERC Online Form
1 so the reviewer can confirm the primary source. No docket number is fabricated - the
proceedings here are real FERC matters; where a precise number is uncertain it is
described and held at low confidence rather than invented. These are public records
captured as cited evidence, consistent with the corpus chain-of-custody discipline.

The campus arrangement classification cross-references the #94 ServingUtility
identification (the campus is a retail customer of AEP Ohio, so PUCO-retail), with the
behind-the-meter co-location case named as the alternative that would instead implicate
FERC. This seam is the regulatory backdrop under the consumer-cost thread (#91): the
campus's grid arrangement determines which regulator sets its price - PUCO retail
(grid-served) vs FERC wholesale (behind-the-meter at a generator).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.grid._registry import utility_identity
from watermark.grid.model import CitedFact
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile, site_reference_path
from watermark.states import state_name, state_puc

log = get_logger(__name__)

# --- Statutory citations (general law - high confidence) ------------------------
_FPA_CITE = (
    "Federal Power Act sections 205/206 (16 U.S.C. 824d/824e); FERC jurisdiction over "
    "wholesale sales in interstate commerce and interstate transmission"
)

# --- Per-site jurisdiction (profile-only, so the FERC seam stays hermetic; #608) -------
# The FERC<->state-PUC seam, the serving-utility identity, and the Form-1 filer all vary by
# site. They are resolved from the active ``SiteProfile`` (eia_state + eia861_utility_number),
# never hardcoded to Ohio/PUCO/AEP — running ``watermark ferc`` under a non-OH site must emit that
# site's regulator (e.g. IN retail = IURC) and serving utility, not Lima's.
#
# Both registries are shared, not local (H2/#1645): the state regulator + readable name come from
# ``watermark.states``, and the Form-1 filer from ``watermark.grid._registry``, which
# ``watermark.grid.utility`` reads for the same utilities' parent/zone provenance. They were two
# hand-synced dicts until a keyset drift lost WPAFB/Xenia their FERC filer (A5/#1638).


class _Jurisdiction(NamedTuple):
    """The active site's FERC<->state-PUC seam inputs, resolved from its ``SiteProfile``."""

    state: str  # "OH"
    state_name: str  # "Ohio"
    puc_short: str  # "PUCO"
    puc_full: str  # "Public Utilities Commission of Ohio (PUCO)"
    utility_short: str  # "AEP Ohio"
    form1_filer: str  # "Ohio Power Company"
    files_form1: bool


def _jurisdiction(settings: Settings) -> _Jurisdiction:
    prof = active_profile(settings)
    state = prof.eia_state
    puc = state_puc(state)
    filer = utility_identity(prof.eia861_utility_number)
    return _Jurisdiction(
        state=state,
        state_name=state_name(state),
        puc_short=puc.short,
        puc_full=puc.full,
        utility_short=filer.short,
        form1_filer=filer.operating_company,
        files_form1=filer.files_form1,
    )


class JurisdictionalBoundary(BaseModel):
    """The cited FERC<->PUCO jurisdictional map for the campus's power arrangement.

    The wholesale/retail line of the Federal Power Act drawn for this campus. Each scope
    statement is a :class:`CitedFact` anchored to the statute (high confidence on the
    general law); ``campus_arrangement`` classifies where the campus most likely falls
    (PUCO retail, grid-served) with the behind-the-meter co-location alternative named.
    """

    model_config = ConfigDict(extra="forbid")

    ferc_scope: CitedFact  # wholesale + interstate transmission + RTO market rules
    puco_scope: CitedFact  # OH retail service + distribution + retail rates
    campus_arrangement: CitedFact  # the classification (PUCO retail unless co-location)
    note: str = ""


class FercDocket(BaseModel):
    """One cited FERC proceeding captured as evidence (a real eLibrary docket).

    A pointer to a public FERC matter relevant to large-load / data-center co-location,
    transcribed from the FERC eLibrary docket. ``status`` records the disposition where
    known (e.g. a rejection). Held as a :class:`CitedFact`-style record - a fabricated
    docket would be worse than omission, so every docket here is a real proceeding and is
    flagged ``verify`` against the cited number; an uncertain precise number is held at
    low confidence rather than asserted.
    """

    model_config = ConfigDict(extra="forbid")

    docket_no: str  # "ER24-2172" | "AD24-11-000" | "" if described not numbered
    title: str
    topic: str  # short tag, e.g. "co-location", "large-load technical conference"
    status: str  # disposition / posture, e.g. "rejected 2024-11-01", "open"
    fact: CitedFact  # the cited statement + citation + confidence


class FercForm1(BaseModel):
    """A FERC Form 1 pointer for the serving utility / transmission owner financials.

    FERC Form 1 is the annual financial & operating report FERC-jurisdictional major
    utilities file (rate base, operating revenues, transmission plant) - the primary
    source for the serving utility's wholesale/transmission financials. This is captured
    as a **cited pointer** (where to obtain it on FERC Online) rather than a transcribed
    figure: no Form-1 number is asserted unless it can be confidently cited. The optional
    ``rate_base`` / ``operating_revenue`` are present only if a transcribed value is
    available, and are then ``reference``-tagged, medium confidence, and ``verify``-flagged.
    """

    model_config = ConfigDict(extra="forbid")

    utility: str  # "Ohio Power Company (AEP Ohio)"
    pointer: CitedFact  # where to obtain the Form 1 (FERC Online), as cited evidence
    rate_base: ProvenancedValue | None = None  # USD, transcribed; omitted unless confident
    operating_revenue: ProvenancedValue | None = None  # USD, transcribed; omitted unless confident


class FercSeam(BaseModel):
    """The assembled FERC regulatory seam (#97): boundary + dockets + Form 1 pointer.

    Bundles the jurisdictional map, the captured large-load / co-location dockets, and
    the FERC Form 1 pointer. The ``note`` cross-references the economics layer: the
    campus's grid arrangement determines which regulator sets its price (PUCO retail vs
    FERC wholesale), the regulatory backdrop the consumer-cost thread (#91) sits under.
    """

    model_config = ConfigDict(extra="forbid")

    boundary: JurisdictionalBoundary
    dockets: list[FercDocket]
    form1: FercForm1
    note: str = ""


def _boundary(j: _Jurisdiction) -> JurisdictionalBoundary:
    retail_cite = (
        "Federal Power Act section 201(b) reserves retail sales and local distribution to "
        f"the states; {j.state_name} retail electric service is {j.puc_short}-regulated (intrastate)"
    )
    utility_xref = (
        f"serving utility identified in #94 (watermark.grid.utility): {j.utility_short} "
        f"({j.form1_filer}), a PJM transmission zone, {j.puc_short}-regulated at retail"
    )
    return JurisdictionalBoundary(
        ferc_scope=CitedFact(
            value=(
                "FERC governs wholesale sales of electricity, interstate transmission, "
                "and RTO/ISO market rules (PJM) - including co-location / behind-the-meter "
                "arrangements at FERC-jurisdictional generators"
            ),
            source="reference",
            citation=_FPA_CITE,
            confidence="high",
        ),
        puco_scope=CitedFact(
            value=(
                f"{j.puc_short} governs {j.state_name} retail electric service, local "
                "distribution, and retail rates / tariffs (intrastate)"
            ),
            source="reference",
            citation=retail_cite,
            confidence="high",
        ),
        campus_arrangement=CitedFact(
            value=(
                f"{j.puc_short} retail (grid-served), unless behind-the-meter co-location: the "
                f"campus is a retail tariff customer of {j.utility_short}, so its service and rate "
                f"fall under {j.puc_short} retail jurisdiction; a behind-the-meter co-location at a "
                "FERC-jurisdictional generator would instead implicate FERC"
            ),
            source="reference",
            citation=(
                f"{utility_xref}; classification of the campus's likely arrangement - "
                "verify against the campus's actual service agreement / tariff filing"
            ),
            confidence="medium",
        ),
        note=(
            f"The FERC<->{j.puc_short} line is the wholesale/retail boundary of the Federal Power "
            f"Act (general law, high confidence). The campus's classification as {j.puc_short} "
            f"retail is the most likely arrangement (grid-served retail customer of "
            f"{j.utility_short} per #94); a behind-the-meter co-location would move the seam to "
            "FERC and is the live policy question the captured dockets address."
        ),
    )


def _dockets() -> list[FercDocket]:
    return [
        FercDocket(
            docket_no="ER24-2172",
            title=(
                "Susquehanna - Amazon Web Services co-location ISA amendment "
                "(Talen Energy / Susquehanna nuclear plant)"
            ),
            topic="co-location",
            status="rejected 2024-11-01",
            fact=CitedFact(
                value=(
                    "FERC rejected the amended interconnection service agreement that "
                    "would have expanded the behind-the-meter co-located data-center load "
                    "at the Susquehanna nuclear plant - a landmark large-load co-location "
                    "ruling raising cost-allocation and reliability questions for "
                    "generator co-location"
                ),
                source="reference",
                citation="FERC eLibrary, Docket ER24-2172; transcribed, verify",
                confidence="medium",
            ),
        ),
        FercDocket(
            docket_no="AD24-11-000",
            title=(
                "Large loads co-located at generating facilities in the PJM region "
                "(FERC technical conference)"
            ),
            topic="large-load technical conference",
            status="technical conference Nov 2024; open policy proceeding",
            fact=CitedFact(
                value=(
                    "FERC's technical conference on large loads (data centers) co-located "
                    "at generators in PJM, examining rate, cost-allocation, and "
                    "reliability treatment of behind-the-meter co-location - the policy "
                    "docket the Susquehanna case fed into"
                ),
                source="reference",
                citation="FERC eLibrary, Docket AD24-11-000; transcribed, verify",
                confidence="medium",
            ),
        ),
        FercDocket(
            docket_no="",
            title="PJM co-location / large-load interconnection policy (broad)",
            topic="co-location / large-load policy",
            status="developing; precise docket not pinned",
            fact=CitedFact(
                value=(
                    "PJM's broader large-load / co-location interconnection policy work "
                    "(stakeholder process and any resulting FERC filing) is the live "
                    "framework for how a campus-scale load would interconnect or co-locate "
                    "- described, not pinned to a precise docket number here"
                ),
                source="reference",
                citation=(
                    "FERC eLibrary / PJM stakeholder record; precise docket not pinned - "
                    "verify and supply the exact number before relying on it"
                ),
                confidence="low",
            ),
        ),
    ]


def _form1(j: _Jurisdiction) -> FercForm1:
    # Form 1 is captured as a cited POINTER, not a transcribed figure: no rate-base or
    # revenue number is asserted unless it can be confidently cited from the filing. The
    # serving utility (e.g. Ohio Power Company / AEP Ohio for Lima) is the #94 identification.
    # A municipal / cooperative system is not FERC Form-1 jurisdictional — say so rather than
    # point at a filing that does not exist.
    if not j.files_form1:
        return FercForm1(
            utility=f"{j.utility_short} (municipal — not FERC Form-1 jurisdictional)",
            pointer=CitedFact(
                value=(
                    f"{j.utility_short} is a municipal electric system and does not file FERC "
                    "Form 1 (FERC Form-1 is filed by FERC-jurisdictional IOUs); its financials "
                    "are reported through its municipal budget / wholesale supplier, not FERC Online"
                ),
                source="reference",
                citation=(
                    f"{j.utility_short} is municipally owned (EIA-861 ownership); municipal systems "
                    "are not FERC Form-1 filers — verify against the utility's annual report"
                ),
                confidence="medium",
            ),
        )
    return FercForm1(
        utility=f"{j.form1_filer} ({j.utility_short})",
        pointer=CitedFact(
            value=(
                f"{j.form1_filer} files FERC Form 1 (annual financial & operating "
                "report) covering rate base, operating revenues, and transmission plant - "
                "the primary source for the serving utility's FERC-jurisdictional "
                "transmission financials; obtain the current vintage from FERC Online"
            ),
            source="reference",
            citation=(
                f"FERC Form 1 (FERC Online), {j.form1_filer}; pointer - transcribe the "
                "specific rate-base / revenue figures from the filing and verify before "
                "relying on them"
            ),
            confidence="medium",
        ),
        # rate_base / operating_revenue intentionally omitted: no figure asserted unless
        # confidently cited (prefer omission over invention - epic #93 data discipline).
    )


def derive_ferc_seam(*, settings: Settings | None = None) -> FercSeam:
    """Assemble the FERC<->state-PUC jurisdictional seam (#97).

    Cross-references the #94 serving-utility identification (for Lima: AEP Ohio / PJM / PUCO)
    - the campus is a retail customer of its serving utility, so it falls under that state's
    retail jurisdiction for its service and tariff. The state retail regulator, the serving
    utility, and the Form-1 filer are resolved per-site from the active ``SiteProfile`` (#608),
    never hardcoded to Ohio/PUCO/AEP. The jurisdictional map is cited to the Federal Power Act;
    the dockets and Form-1 pointer are cited evidence flagged for verification.

    Hermetic: the seam is structural / regulatory and reads no numeric connector — the per-site
    inputs come from the profile (eia_state + eia861_utility_number).
    """
    settings = settings or get_settings()
    j = _jurisdiction(settings)

    boundary = _boundary(j)
    dockets = _dockets()
    form1 = _form1(j)

    log.info(
        "grid.ferc.seam",
        arrangement=f"{j.puc_short} retail (grid-served), unless behind-the-meter co-location",
        dockets=[d.docket_no or d.title for d in dockets],
    )
    return FercSeam(
        boundary=boundary,
        dockets=dockets,
        form1=form1,
        note=(
            f"FERC regulatory seam (#97). The FERC<->{j.puc_short} boundary is the wholesale/retail "
            "line of the Federal Power Act: FERC = wholesale + interstate transmission + "
            "PJM market rules (and behind-the-meter co-location at FERC-jurisdictional "
            f"generators); {j.puc_short} = {j.state_name} retail service, distribution, and retail "
            f"rates. The campus is most likely {j.puc_short}-retail (grid-served customer of "
            f"{j.utility_short}, #94). This determines which regulator sets the campus's price - "
            f"{j.puc_short} retail vs FERC wholesale - the regulatory backdrop the consumer-cost "
            "thread (#91) sits under. Dockets and the Form-1 pointer are public records captured "
            "as cited evidence, flagged for verification against FERC eLibrary / FERC Online."
        ),
    )


def _reference_path(settings: Settings) -> Path:
    """The active site's FERC-seam path (#1639/B1). Per-site because the seam embeds per-site
    content (the FERC↔state-PUC jurisdiction, the serving utility) — a slug-scoped default
    unless the profile pins one (Lima keeps the un-slugged legacy path)."""
    return site_reference_path(
        settings, active_profile(settings).ferc_relpath, subdir="ferc", filename="ferc-seam.yaml"
    )


def write_ferc_seam(seam: FercSeam, *, settings: Settings | None = None) -> str:
    """Persist the FERC seam as committed reference YAML for the active site; return the path."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(seam.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("grid.ferc.wrote", path=str(path))
    return str(path)


def load_ferc_seam(settings: Settings | None = None) -> FercSeam | None:
    """Read the committed FERC-seam YAML for the active site, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return FercSeam.model_validate(data)
