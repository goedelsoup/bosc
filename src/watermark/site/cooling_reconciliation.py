"""The ``cooling-reconciliation`` bundle feed (#1805, epic #1803 P2).

The cooling-cycling reconciliation harness (epic #1676: A3 #1679 the claim-vs-documented
account, A4 #1680 the independent corroborators, B1-B3 the per-site provenance slots) writes
one committed cross-site artifact — ``data/reference/oepa/cooling-reconciliation.yaml`` —
that until now nothing bundle-side read: the study's water chapter quoted its outcome as
hand-curated MDX prose, which can drift from the artifact it quotes.

This module lifts **the site's own candidate row(s)** into a per-site object feed. It is a
reader, not a second harness: rows are validated back through the producer's own
:class:`~watermark.hydrology.cooling_reconcile.ReconciliationRecord` model and shipped
verbatim, so the feed is byte-consistent with the committed reference artifact by
construction (the enclave/rsei "the feed IS the model" pattern).

Two hard rules:

- **Never another site's account.** The artifact is a flat cohort list keyed by each row's
  own ``site``; the loader filters to ``settings.site`` and self-skips (returns ``None``)
  when the site has no row — the rsei/drawdown present-but-empty rule (#1364), so a
  non-cohort site ships no feed rather than an empty shell.
- **The Intel positive control never ships.** The cohort carries one constructed
  calibration row (``is_control: true``, sited ``new-albany`` — openly evaporative, built so
  the harness must classify it ``corroborated``). It is a calibration vector, not site
  data, and ``new-albany`` is itself a registered bundle — so the loader excludes control
  rows explicitly rather than relying on the site filter alone. New Albany's **live** row
  (B6, #1686 — Intel's real, ``route_blind`` record) is a different row and does ship: the
  exclusion is of the constructed vector, not of the site.

**The discipline travels as data.** The artifact's meta block carries the harness's rules
in prose; the renderer-facing distillation rides the feed as ``caveats`` the consumer MUST
show (the ``gridBackdrop.ts`` discipline: callers render, never drop). A test pins each
caveat's key phrase to the committed meta prose so the two can't drift.
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings
from watermark.hydrology.cooling_reconcile import RECONCILIATION_RELPATH, ReconciliationRecord

# The renderer-facing distillation of the artifact's meta `discipline` prose — carried on
# every site's feed as MUST-render caveats. Each line's key phrase is pinned to the
# committed meta text by `tests/test_cooling_reconciliation_feed.py`.
DISCIPLINE_CAVEATS: tuple[str, ...] = (
    "The harness recommends; it never mutates the pinned cooling model — re-archetyping is "
    "a reviewed edit with the instrument cited.",
    "A back-solved cycles-of-concentration is an [inference] bracket, never a headline scalar.",
    "A gap (no documented makeup or blowdown) is an [open] records-request lead — never read "
    "as 'confirmed dry'.",
    "A reservation ceiling (a will-serve / water-agreement figure) is not a "
    "discharge/withdrawal instrument — it keeps the archetype pin and is never collapsed "
    "into a headline consumptive figure.",
    "An operator self-report lands on its own disclosed_* slot, never on documented_*, and "
    "cannot upgrade the claim's source.",
    "An instrument that cannot reach a facility returns an absence of jurisdiction, not a "
    "measurement — a municipally-supplied, sewer-discharging campus reads ~0 in the withdrawal "
    "registry and the discharge record by construction, and that ~0 never corroborates a claim.",
    "A documented withdrawal that is not the cooling account (construction-phase water) is kept "
    "on its own slot, and a prediction the harness could not derive is shown as refused, never "
    "as zero.",
    "The corroborators (air-permit PM, Tier II chemistry) are secondary — recorded and "
    "reconciled against the claim, never the sole basis for a re-archetype and never "
    "changing the outcome.",
)


class CoolingReconciliationFeed(BaseModel):
    """The site's own claim-vs-record cooling account, as the bundle ships it.

    ``candidates`` are the committed artifact's rows for this site, verbatim (each an
    already-provenanced ``ReconciliationRecord`` — claim, predicted account at screening
    grade, the documented/reserved/disclosed slots, outcome + tag + finding, the
    records-sought lead, the secondary corroborator stances). ``caveats`` are the harness's
    discipline rules; a renderer must show them, not drop them.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    asof: str  # the artifact meta's asof — the reconciliation's own date, not the export's
    source: str  # the committed artifact + its regenerate command (the citable provenance)
    caveats: list[str]
    candidates: list[ReconciliationRecord]


def load_cooling_reconciliation(settings: Settings) -> CoolingReconciliationFeed | None:
    """The site's own reconciliation rows, or ``None`` when it has none to ship.

    ``None`` for a site outside the cohort, for a site whose only row is the constructed
    control, and when the committed artifact is absent — the feed self-skips rather than
    shipping an empty shell or another site's account.
    """
    path = settings.data_dir / RECONCILIATION_RELPATH
    if not path.exists():
        return None
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    meta = doc.get("meta") or {}
    rows = [
        r
        for r in (doc.get("candidates") or [])
        if r.get("site") == settings.site and not r.get("is_control")
    ]
    if not rows:
        return None
    return CoolingReconciliationFeed(
        site=settings.site,
        asof=str(meta.get("asof") or ""),
        source=f"data/{RECONCILIATION_RELPATH} — regenerate: {meta.get('regenerate') or 'watermark cooling-reconcile --write'}",
        caveats=list(DISCIPLINE_CAVEATS),
        candidates=[ReconciliationRecord.model_validate(r) for r in rows],
    )


__all__ = ["DISCIPLINE_CAVEATS", "CoolingReconciliationFeed", "load_cooling_reconciliation"]
