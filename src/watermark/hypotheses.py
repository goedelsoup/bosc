"""The boom-origin hypotheses — the third axis, as first-class data.

BOSC asks one question across a network of watershed-point sites: *what explains the
data-center boom?* The platform holds several competing readings of that question — the
**hypotheses**:

* **H1 Water & Coercion** — compute lands where it can pull power and water; the CWA
  discharge backstop structurally compels municipal acceptance. The reference thesis,
  fully assembled at Lima.
* **H2 Defense & Federal Enclave** — the build-out tracks arsenals, air bases, federal
  research, and the CHIPS program; and a capture sub-thesis asks whether the defense base
  distorts the local economy the datacenter lands in. *Emerging — under test.*
* **H3 Consumer Surveillance** — the operators behind shell LLCs, the public-subsidy
  stack that pulls them in, and the consumer surveillance apparatus the compute serves.
  *Emerging — under test.*

A :class:`Hypothesis` is the *content* of one reading (claim, thesis, the evidence it
predicts); presentation (accent colors, column widths) stays in the frontend. A
:class:`HypothesisAssessment` is the join object this module exists to make real: one
``(site x hypothesis)`` **evidence cell**, carrying a signal strength, an evidentiary
:attr:`~HypothesisAssessment.tag`, the per-hypothesis fields, and — the upgrade over the
old hardcoded TypeScript — a :class:`Citation` for provenance. Cells are committed under
``data/hypotheses/<hypothesis-id>/<site-slug>.yaml`` (hand-authored, or promoted from a
``watermark research run --recipe hypothesis-assessment``).

This is **not** :class:`watermark.hydrology.hypothesis.Hypothesis`, which tags water-balance
*scenarios* by level (macro/local/site). That one frames the Lima loop's numbers; this
one frames the *network* against the origin of the boom. They are deliberately separate.

The peer modules are :mod:`watermark.sites` (the site axis) and :mod:`watermark.research` (the
agent that fills cells). Mirrors ``watermark.sites`` conventions: a frozen registry, a
``data/`` loader, and a readiness lint surfaced by the ``watermark hypotheses`` CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, computed_field

from watermark.config import Settings, get_settings
from watermark.provenance import Confidence as Confidence
from watermark.provenance import SourceKind as SourceKind
from watermark.provenance import source_is_verified
from watermark.sites import SITES

# Signal strength of a site's nexus under a hypothesis (orthogonal to `tag`: `signal` is
# how loud the nexus is, `tag` is whether the facts in the cell are documented or inferred).
Signal = Literal["anchor", "strong", "moderate", "watch"]
# Evidentiary discipline tag for the cell's facts (mirrors the [verified]/[inference]/[open]
# vocabulary in docs/investigative-method): a documented fact, an inferred connection, or an
# open question. NOT a verdict on the hypothesis — a federal nexus is a signal, not proof.
EvidenceTag = Literal["verified", "inference", "open"]
# Sub-thesis tag: classifies what *kind of claim* the cell is making — the investigative
# frame, orthogonal to signal (loudness) and tag (evidentiary weight). Optional; a cell
# without one is valid. Vocabulary agreed in #905:
#   coercion  — a regulatory/structural mechanism that compels locality acceptance
#   end-use   — what the compute is actually for (application class)
#   capture   — economic/political capture (subsidies, CRA/PILOT, abatements)
#   opacity   — concealment via shell LLCs, redacted records, beneficial-ownership gaps
#   nexus     — the specific institutional/regulatory framework enabling the site
SubThesis = Literal["coercion", "end-use", "capture", "opacity", "nexus"]
HypothesisStatus = Literal["reference", "emerging"]
# SourceKind / Confidence are shared from watermark.provenance (#605) — the lightweight core that
# watermark.site.feeds.Citation + hydrology.ProvenancedValue also speak, so the Phase-2 feed map
# stays lossless without this core module importing the heavy watermark.site package.


class Citation(BaseModel):
    """Where a cell's facts came from — the provenance the old hardcoded table lacked.

    Field-compatible with :class:`watermark.site.feeds.Citation` so a cell exports to the
    content bundle without translation. ``source_kind`` says what kind of artifact backs
    the fact; ``verified`` is derived (a record or a live gauge), so a consumer never
    recomputes it. An inferred connection uses ``source_kind='assumption'``.
    """

    model_config = ConfigDict(extra="forbid")

    source: str | None = None  # repo-relative artifact path, dataset label, or doc id
    source_kind: SourceKind = "reference"
    page: int | None = None
    confidence: Confidence = "medium"
    note: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        """True when grounded in a record or a live gauge ([verified] in prose)."""
        return source_is_verified(self.source_kind)


class Hypothesis(BaseModel):
    """One reading of the boom — the content of a directory hypothesis (frozen reference value).

    Presentation (accent palette, grid fractions, column labels) is the frontend's; this
    holds the substance: the claim, the thesis, the taxonomy a cell is scored against, and
    :attr:`predicted_evidence` — what would confirm or strengthen it, which scaffolds the
    ``hypothesis-assessment`` research recipe's prompt.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str  # "water" | "defense" | "surveillance" — matches the frontend HypothesisId key
    number: str  # "H1" | "H2" | "H3"
    name: str
    claim: str
    thesis: str
    status: HypothesisStatus
    # The signal levels and assessment taxonomy a cell may use under this hypothesis.
    signals: tuple[Signal, ...] = ("anchor", "strong", "moderate", "watch")
    groups: tuple[str, ...] = ()
    # The per-hypothesis cell columns (e.g. defense: nexus, linkage). A cell's `fields`
    # keys must be a subset of these (the `check` lint enforces it).
    fields: tuple[str, ...] = ()
    related_docs: tuple[str, ...] = ()  # the narrative docs that argue this thesis
    predicted_evidence: tuple[str, ...] = ()  # what would confirm/strengthen it (agent prompt)


class HypothesisAssessment(BaseModel):
    """One ``(site x hypothesis)`` evidence cell — the join object joining the three axes.

    A site's standing under one hypothesis: a :attr:`signal` strength, an evidentiary
    :attr:`tag`, the hypothesis's taxonomy :attr:`group`, the per-hypothesis :attr:`fields`,
    and ≥1 :class:`Citation` (required for any non-``open`` cell). ``site`` is a slug — it
    may name a *tracking* candidate not yet in :data:`watermark.sites.SITES` (the frontend lists
    tracked points too), so site membership is not hard-enforced here.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    hypothesis: str
    signal: Signal | None = None
    tag: EvidenceTag = "open"
    sub_thesis: SubThesis | None = None
    group: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)


# --- the registry (ported from web/packages/core/src/directory.ts HYPOTHESIS_VIEW) --------------
HYPOTHESES: dict[str, Hypothesis] = {
    "water": Hypothesis(
        id="water",
        number="H1",
        name="Water & Coercion",
        claim="Where discharge becomes leverage.",
        thesis=(
            "The original thesis: hyperscale compute lands where it can pull power and "
            "water, and a data center's intake, discharge, and downstream effects are "
            "basin facts. Sites nest by drainage — two divides, nine basins. Lima is the "
            "live, fully-assembled reference. "
            "A coercion sub-thesis (#903): in municipalities with declining populations, "
            "the receiving WWTP may be running lean on influent — below the biological-treatment "
            "minimum that keeps it in NPDES compliance. A datacenter's high-volume, consistent "
            "discharge provides the flow buffer the plant needs, structurally compelling "
            "municipal acceptance. The Clean Water Act is the backstop that makes the need "
            "non-negotiable."
        ),
        status="reference",
        # H1 is rendered from the site registry + network (by drainage), not from cells.
        # Cells are enabled for the coercion sub-thesis (#903) so
        # per-site WWTP lean-flow evidence can be committed and tracked.
        groups=("coercion",),
        fields=("wwtp", "gap"),
        related_docs=("docs/HYDROLOGY.md", "docs/COURSE.md"),
        predicted_evidence=(
            "cooling consumptive draw measured against the receiving water's cited 7Q10",
            "an NPDES discharge to an already effluent-dominated stream",
            "a paved campus footprint's pre/post-development stormwater delta",
            "a serving utility / PJM zone that makes the load economically siteable",
            "ECHO DMR showing the receiving WWTP's actual annual influent below its design-flow minimum",
            "a utility service agreement or NPDES commitment that quantifies the datacenter's "
            "discharge volume relative to the WWTP's lean-flow deficit",
            "OEPA enforcement correspondence or sanitary system capacity study citing the "
            "same deficit the datacenter discharge would address",
        ),
    ),
    "defense": Hypothesis(
        id="defense",
        number="H2",
        name="Defense & Federal Enclave",
        claim="Where the build-out meets federal land and the defense base.",
        thesis=(
            "A second reading: the same map tracks arsenals, air bases, federal research "
            "and the CHIPS build — enclaves where federal jurisdiction, clearance, and "
            "defense supply chains concentrate. Newly opened; most sites are not yet "
            "assessed, and a federal nexus is a signal, not a verdict. "
            "A capture sub-thesis (#1663): the enclave is not only geography, it is an "
            "economic structure — federal payroll and prime-award obligations concentrated in "
            "one county, land held by the United States and therefore off the local tax rolls, "
            "and the abatement / PILOT / public-benefit instruments layered on the ground "
            "around it. The reading it tests is whether the defense base *distorts* the local "
            "economy the datacenter then lands in, or merely sits beside it."
        ),
        status="emerging",
        # `capture` is the economic reading's own taxonomy group, added alongside the three
        # geographic ones (#1663, ME-D) — a site whose defense story is economic rather than
        # locational lands there rather than being forced into `supply` or dropped to `watch`.
        groups=("arsenal", "federal", "supply", "capture", "watch"),
        # `nexus`/`linkage` carry the geographic reading; `capture`/`federal_flow` carry the
        # economic one. They are independent of the cell's single `sub_thesis` frame, so a cell
        # whose primary frame is the arsenal nexus can still state what the money does.
        fields=("nexus", "linkage", "capture", "federal_flow"),
        related_docs=("docs/defense-nexus.md", "docs/ECONOMICS.md"),
        predicted_evidence=(
            "a co-located or adjacent arsenal, air base, or federal research lab",
            "a CHIPS / federal semiconductor or defense-supply designation",
            "a documented authorization posture (FedRAMP / DoD IL clearance level)",
            "a federal-ownership QCEW employment / wage share the county's private-ownership "
            "sector mix structurally cannot show (the ME-B blind spot, #1661)",
            "prime-award obligations resolving to a corridor entity by verified UEI, with the "
            "defense-vs-civilian split of those dollars (#1662)",
            "a tax abatement, PILOT, or public-benefit agreement on defense-adjacent land — or "
            "federally-held acreage carrying assessed value but no local tax duty",
        ),
    ),
    "surveillance": Hypothesis(
        id="surveillance",
        number="H3",
        name="Consumer Surveillance",
        claim="What the compute is for, who it watches, and who's paying.",
        thesis=(
            "A third reading: the operators behind shell LLCs, the public-subsidy stack "
            "that pulls them in, and the capital and data flows the facilities sit on. The "
            "consumer-surveillance thesis — opening now, mostly under "
            "investigation, with Lima's abatement on record. "
            "An end-use sub-thesis (#904): these facilities are infrastructure nodes in a "
            "consumer surveillance apparatus — behavioral tracking, financial-transaction "
            "processing, or similar mass-scale surveillance of individual consumer activity, "
            "financed in part by the public subsidies the same communities provide."
        ),
        status="emerging",
        groups=("onrecord", "subsidy", "watch"),
        fields=("operator", "capital", "end_use"),
        related_docs=("docs/ECONOMICS.md",),
        predicted_evidence=(
            "a named operator behind a shell LLC (deed / SOS / LEI trail)",
            "a public-subsidy instrument on record (CRA / TIF / enterprise-zone abatement)",
            "a capital or data-flow linkage tying the site to a known operator",
            "the operator's active consumer-facing product lines at the time of the permit "
            "application (10-K / AWS availability-zone announcement / product launch timeline)",
            "a product classification tying the compute to a consumer surveillance application "
            "class: behavioral-advertising, financial-transaction, consumer-credit, "
            "AI-inference over consumer data",
        ),
    ),
}


def get_hypothesis(hid: str) -> Hypothesis:
    """The :class:`Hypothesis` for ``hid``; raises ``KeyError`` if unknown."""
    return HYPOTHESES[hid]


# --- the committed assessment store (data/hypotheses/<hid>/<site>.yaml) ---------------------
def assessment_path(hid: str, site: str, *, settings: Settings | None = None) -> Path:
    """Where a single ``(site x hypothesis)`` cell is committed."""
    settings = settings or get_settings()
    return settings.hypotheses_dir / hid / f"{site}.yaml"


def load_assessments(*, settings: Settings | None = None) -> list[HypothesisAssessment]:
    """Load every committed evidence cell under ``data/hypotheses/`` (sorted, stable)."""
    settings = settings or get_settings()
    root = settings.hypotheses_dir
    if not root.exists():
        return []
    cells: list[HypothesisAssessment] = []
    for path in sorted(root.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cells.append(HypothesisAssessment.model_validate(data))
    return cells


def assessments_for(hid: str, *, settings: Settings | None = None) -> list[HypothesisAssessment]:
    """The cells assessed under one hypothesis (``hid``)."""
    return [c for c in load_assessments(settings=settings) if c.hypothesis == hid]


# --- readiness lint (the `watermark hypotheses check` gate) -------------------------------------
class AssessmentFinding(BaseModel):
    """One lint problem with a committed cell (surfaced by ``watermark hypotheses check``)."""

    model_config = ConfigDict(extra="forbid")

    site: str
    hypothesis: str
    kind: Literal[
        "unknown-hypothesis", "bad-group", "bad-field", "missing-citation", "untracked-site"
    ]
    detail: str


def lint_assessments(*, settings: Settings | None = None) -> list[AssessmentFinding]:
    """Validate the committed cells structurally against the registry.

    Hard problems (a reviewer must fix): a cell's hypothesis isn't registered, its
    ``group`` isn't in the hypothesis taxonomy, a ``fields`` key isn't declared by the
    hypothesis, or a non-``open`` cell carries no citation. ``untracked-site`` is a soft
    note — a cell may legitimately name a tracking candidate not yet in ``SITES``.
    """
    findings: list[AssessmentFinding] = []
    for c in load_assessments(settings=settings):
        hyp = HYPOTHESES.get(c.hypothesis)
        if hyp is None:
            findings.append(
                AssessmentFinding(
                    site=c.site,
                    hypothesis=c.hypothesis,
                    kind="unknown-hypothesis",
                    detail=f"not in HYPOTHESES (known: {sorted(HYPOTHESES)})",
                )
            )
            continue  # can't check group/fields against an unknown taxonomy
        if c.group is not None and c.group not in hyp.groups:
            findings.append(
                AssessmentFinding(
                    site=c.site,
                    hypothesis=c.hypothesis,
                    kind="bad-group",
                    detail=f"{c.group!r} not in {hyp.groups}",
                )
            )
        for key in c.fields:
            if key not in hyp.fields:
                findings.append(
                    AssessmentFinding(
                        site=c.site,
                        hypothesis=c.hypothesis,
                        kind="bad-field",
                        detail=f"{key!r} not a declared field {hyp.fields}",
                    )
                )
        if c.tag != "open" and not c.citations:
            findings.append(
                AssessmentFinding(
                    site=c.site,
                    hypothesis=c.hypothesis,
                    kind="missing-citation",
                    detail=f"tag={c.tag!r} requires ≥1 citation (only 'open' may have none)",
                )
            )
        if c.site not in SITES:
            findings.append(
                AssessmentFinding(
                    site=c.site,
                    hypothesis=c.hypothesis,
                    kind="untracked-site",
                    detail="site has no SiteProfile yet (a tracking candidate) — informational",
                )
            )
    return findings
