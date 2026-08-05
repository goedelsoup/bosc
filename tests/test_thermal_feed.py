"""The `thermal` content-bundle feed (#1719, epic #1715 Phase 4) — the receiving-water
temperature-rise / CWA §316(a) screen reaching the frontend.

Phases 1-3 built the criteria table, the screen, and the ECHO-DMR validation, but the result
reached only a committed reference file. This asserts the publication: the screen lands in the
bundle intact, the modelled-vs-observed distinction the screen is careful about survives the
export, and a peer site does **not** inherit the reference site's corridor.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watermark.site.feeds import CONTRACT_VERSION

_CV = "2.0.0"


def _manifest(bundle: Path) -> dict[str, Any]:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def _thermal(bundle: Path) -> dict[str, Any] | None:
    """The bundle's thermal feed payload, or ``None`` when the site emits no screen."""
    ref = next((f for f in _manifest(bundle)["feeds"] if f["name"] == "thermal"), None)
    if ref is None:
        return None
    assert ref["kind"] == "object"
    assert ref["count"] == 1
    return json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))


def test_contract_version_bumped_for_the_thermal_feed() -> None:
    """One new feed → MINOR (1.40.0 → 1.41.0), back-compatible: a reader that doesn't know
    `thermal` is unaffected, and a pre-1.41 bundle simply has no thermal screen to render."""
    assert CONTRACT_VERSION == _CV


def test_reference_export_emits_the_thermal_screen(lima_bundle: Path) -> None:
    assert _manifest(lima_bundle)["contract_version"] == _CV
    feed = _thermal(lima_bundle)
    assert feed is not None, "the reference build must publish the thermal screen"
    assert feed["meta"]["site"] == "lima"
    assert feed["meta"]["receiving_water"] == "Ottawa River"
    # The Ohio criterion is per geographic ZONE, not per aquatic-life-use column (#1716).
    assert feed["meta"]["zone_id"] == "lake_erie_basin_general"
    assert "3745-1-35" in feed["meta"]["zone_rule"]
    assert feed["screens"], "a screen with no rows is not publishable"


def test_the_feed_keeps_modelled_and_observed_heat_loads_distinct(lima_bundle: Path) -> None:
    """The screen's load-bearing discipline: a `data_center` row's heat load is an INFERENCE about
    a facility that is not yet discharging, a `permitted_discharger` row's is the permittee's own
    reported measurement. The frontend can only honour that if `kind` survives the export — with
    the scenarios/calibration on the modelled side and the DMR block on the observed side."""
    feed = _thermal(lima_bundle)
    assert feed is not None
    kinds = {row["kind"] for row in feed["screens"]}
    assert kinds == {"data_center", "permitted_discharger"}

    modelled = [r for r in feed["screens"] if r["kind"] == "data_center"]
    observed = [r for r in feed["screens"] if r["kind"] == "permitted_discharger"]
    assert modelled and observed

    for row in modelled:
        # The three heat-partition scenarios (#1718) and the derived-vs-observed cross-check.
        assert {s["scenario"] for s in row["scenarios"]} == {
            "conservative_bound",
            "once_through",
            "evaporative_blowdown",
        }
        assert row["calibration"] is not None
    for row in observed:
        assert row["npdes_id"], "an observed row is identified by its permit"
        assert row["dmr"] is not None, "an observed row's load comes from its own reported record"
        assert not row["scenarios"], "a measurement carries no modelled heat partition"


def test_the_published_screen_carries_the_316a_trigger_and_its_caveats(lima_bundle: Path) -> None:
    """The finding the phase exists to publish, plus the caveats that keep it a screen: the
    Ottawa's near-zero thermal assimilative capacity means the fully-mixed rise exceeds the Ohio
    daily-max criterion — a §316(a) / thermal-mixing-zone question, NOT an automatic violation."""
    feed = _thermal(lima_bundle)
    assert feed is not None
    assert any(row["flag"] == "critical" for row in feed["screens"])
    caveats = " ".join(feed["meta"]["caveats"])
    assert "§316(a)" in caveats
    assert "NOT an automatic violation" in caveats
    # The permittees whose OWN reported effluent sits over Ohio's criterion — the corridor's
    # measured heat, published alongside the modelled campus load.
    assert feed["meta"]["permits_over_daily_max_criterion"]


def test_a_peer_site_does_not_inherit_the_reference_corridor(
    site_bundle: Callable[[str], Path],
) -> None:
    """The screen file lives in the basin-shared `reference/hydrology/` tree under one un-slugged
    name, so an ungated export would hand Fort Wayne the Ottawa River, Ohio's zone G criterion, and
    Lima's permittees as its own. The feed is gated on the artifact's own `meta.site`."""
    assert _thermal(site_bundle("fort-wayne")) is None
