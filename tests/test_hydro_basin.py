"""Basin-wide low-flow assimilative screen over the ECHO Maumee POTW inventory.

Hermetic: the screen reads only committed reference data (the cited + derived 7Q10
tables and the ECHO POTW inventory) — no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.hydrology import basin

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data_settings() -> Settings:
    return Settings(data_dir=REPO_ROOT / "data")


def test_derived_low_flows_loaded(data_settings: Settings) -> None:
    derived = basin.load_derived_low_flows(settings=data_settings)
    maumee = derived[basin._norm("maumee river")]
    assert maumee.source == "derived"
    assert maumee.unit == "cfs"
    assert maumee.value == pytest.approx(114.15, abs=0.5)  # USGS 04193500 LP3 7Q10
    # Every St. Joseph surface form resolves to the same derived value.
    sj = {basin._norm(a) for a in ("st joseph river", "st joseph r", "st. joseph river")}
    assert sj <= set(derived)
    assert len({derived[k].value for k in sj}) == 1


def test_basin_screen_coverage(data_settings: Settings) -> None:
    screen = basin.check_basin_assimilative(settings=data_settings)
    c = screen.coverage
    assert c.total == 129
    assert c.screened == len(screen.checks) == 7
    # Honest coverage: most of the basin is unscreenable, surfaced explicitly.
    assert c.no_receiving_water == 77
    assert c.screened + c.no_receiving_water + c.no_7q10 + c.no_design_flow == c.total
    # The cited Lima-loop violation (American Bath -> Pike Run) is still caught.
    cited = [ch for ch in screen.checks if ch.design_low_flow.source == "document"]
    assert any("PIKE RUN" in ch.receiving_water.upper() for ch in cited)
    assert c.violations >= 1
    # Major mainstem dischargers now screen via derived 7Q10 (e.g. Defiance -> Maumee).
    derived = [ch for ch in screen.checks if ch.design_low_flow.source == "derived"]
    assert len(derived) >= 5
    assert all(ch.discharge.source == "reference" for ch in screen.checks)


def test_screen_omits_tributary_compounds(data_settings: Settings) -> None:
    # A discharger whose PRIMARY receiver is a ditch must not borrow a downstream
    # mainstem's larger 7Q10 (that would overstate dilution). Omit, don't guess.
    lookup = basin.load_derived_low_flows(settings=data_settings)
    assert basin._match_low_flow("Baldwin Ditch, Maumee River", lookup) is None
    assert basin._match_low_flow("Maumee River", lookup) is not None
    # The St. Joseph typo/synonym compound still matches on its primary form.
    assert basin._match_low_flow("ST JOSEPH R, ST JOSEPH RIVER", lookup) is not None
