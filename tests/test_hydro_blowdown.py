"""OHD000001 general-permit coverage + facility-own blowdown status (#1678).

Hermetic: the resolver reads the site registry and a cited permit-lifecycle constant — no
network, no fixture. The gating fact under test is that OHD000001 is still a *draft* general
permit, so every candidate resolves to ``not_available`` (a [verified] cited absence), and the
committed cohort artifact validates against the models.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from watermark.config import Settings
from watermark.hydrology import blowdown


def _candidate(**kw: object) -> blowdown.Candidate:
    base: dict[str, object] = {
        "site": "test-site",
        "facility": "Test Data Center",
        "cooling_claim": "closed_loop_dry",
        "cooling_source": "reference",
        "cooling_citation": "[reference] operator FAQ closed-loop claim",
    }
    base.update(kw)
    return blowdown.Candidate(**base)  # type: ignore[arg-type]


def test_general_permit_effective_property() -> None:
    # The committed OHD000001 constant is draft -> not effective (the coverage gate).
    assert blowdown.OHD000001.state is blowdown.GeneralPermitState.DRAFT
    assert blowdown.OHD000001.effective is False
    assert (
        blowdown.OHD000001.confidence == "high"
    )  # lifecycle facts from the permit's public notice
    # Frozen: the shared default must not be mutable in place (it backs resolve_coverage defaults).
    with pytest.raises(ValidationError):
        blowdown.OHD000001.asof = "2099-01-01"  # type: ignore[misc]
    # A permit is effective only when its state is EFFECTIVE *and* it carries an effective date.
    issued = blowdown.OHD000001.model_copy(
        update={"state": blowdown.GeneralPermitState.EFFECTIVE, "effective_date": "2026-09-01"}
    )
    assert issued.effective is True
    stateless = blowdown.OHD000001.model_copy(
        update={"state": blowdown.GeneralPermitState.EFFECTIVE, "effective_date": None}
    )
    assert stateless.effective is False  # effective state but no date -> not in force


def test_draft_permit_resolves_every_candidate_not_available() -> None:
    cov = blowdown.resolve_coverage(_candidate())
    assert cov.ohd000001_status is blowdown.CoverageStatus.NOT_AVAILABLE
    assert cov.tag == "[verified]"  # the draft-gated absence is a verified fact about the permit
    assert cov.confidence == "high"  # tracks the tag strength (for A3 structural filtering)
    assert cov.facility_own_discharge is blowdown.FacilityOwnDischarge.UNKNOWN
    assert "draft general permit" in cov.finding
    assert "C2 records request" in cov.finding  # the absent-permit gap becomes a records lead


def test_facility_own_permit_present_when_id_on_record() -> None:
    cov = blowdown.resolve_coverage(
        _candidate(facility_npdes_id="OHD9999999", blowdown_dmr_relpath="extracted/x/foo.dmr.yaml")
    )
    assert cov.facility_own_discharge is blowdown.FacilityOwnDischarge.PRESENT
    assert cov.facility_npdes_id == "OHD9999999"
    assert "OHD9999999" in cov.finding
    assert "foo.dmr.yaml" in cov.finding


def test_effective_permit_leaves_authorization_lookup_as_open_seam() -> None:
    # Once the permit issues, covered/not-sought needs a per-facility authorization lookup that is
    # not wired while it is draft — the resolver returns no_record/[open], never a fabricated status.
    issued = blowdown.OHD000001.model_copy(
        update={"state": blowdown.GeneralPermitState.EFFECTIVE, "effective_date": "2026-09-01"}
    )
    cov = blowdown.resolve_coverage(_candidate(), gp=issued)
    assert cov.ohd000001_status is blowdown.CoverageStatus.NO_RECORD
    assert cov.tag == "[open]"
    assert cov.confidence == "low"  # unresolved seam -> low confidence


def test_closed_loop_cohort_is_registry_derived() -> None:
    cands = blowdown.closed_loop_candidates(settings=Settings())
    assert cands, "expected at least one closed-loop-claiming facility in the registry"
    # Every candidate discloses a recirculating/closed archetype — nothing else is swept in.
    assert all(c.cooling_claim in {"closed_loop_dry", "hybrid_adiabatic"} for c in cands)
    sites = {c.site for c in cands}
    assert "urbana" in sites  # a known closed-loop-dry pin (#1327)
    # A facility whose cooling method is UNKNOWN is NOT a candidate (Troy-Piqua, pending #1486).
    assert "troy-piqua" not in sites
    # Deterministic ordering for a stable artifact.
    assert [c.site for c in cands] == sorted(c.site for c in cands)


def test_coverage_document_shape_and_cohort_resolution() -> None:
    gp, coverages = blowdown.resolve_cohort(settings=Settings())
    assert coverages
    assert all(c.ohd000001_status is blowdown.CoverageStatus.NOT_AVAILABLE for c in coverages)
    doc = blowdown.coverage_document(gp, coverages)
    assert doc["general_permit"]["permit_id"] == "OHD000001"
    assert doc["general_permit"]["effective"] is False
    assert doc["general_permit"]["confidence"] == "high"
    assert doc["meta"]["regenerate"] == "watermark oepa coverage --write"
    assert len(doc["candidates"]) == len(coverages)
    # Each candidate row round-trips back into the model (the artifact stays schema-valid).
    for row in doc["candidates"]:
        blowdown.BlowdownCoverage.model_validate(row)


def test_write_coverage_round_trips(tmp_path: Path) -> None:
    gp, coverages = blowdown.resolve_cohort(settings=Settings())
    out = tmp_path / "coverage.yaml"
    blowdown.write_coverage(blowdown.coverage_document(gp, coverages), out=out)
    reloaded = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert reloaded["general_permit"]["state"] == "draft"
    assert [blowdown.BlowdownCoverage.model_validate(r) for r in reloaded["candidates"]]


def test_committed_artifact_matches_the_resolver() -> None:
    # The committed data/reference/oepa/ohd000001-coverage.yaml is regenerable and schema-valid,
    # and its candidate set matches what the resolver produces today (no hand-drift).
    path = Path("data/reference/oepa/ohd000001-coverage.yaml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["general_permit"]["permit_id"] == "OHD000001"
    committed = {c["site"] for c in doc["candidates"]}
    live = {c.site for c in blowdown.closed_loop_candidates(settings=Settings())}
    assert committed == live
    for row in doc["candidates"]:
        blowdown.BlowdownCoverage.model_validate(row)
