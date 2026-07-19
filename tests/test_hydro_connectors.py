"""NWIS connector + the offline cache/fixture machinery (hermetic, no network)."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import nwis
from watermark.hydrology.connectors._cache import HydroOfflineError, cache_key


def test_fetch_streamflow_from_fixture(hydro_settings: Settings) -> None:
    readings = nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
    by_param = {r.parameter_cd: r for r in readings}
    assert by_param[nwis.DISCHARGE_CFS].value == pytest.approx(36.3)
    assert by_param[nwis.DISCHARGE_CFS].unit  # has a unit string
    assert "Ottawa River at Lima" in by_param[nwis.DISCHARGE_CFS].name


def test_streamflow_captures_provisional_qualifier(hydro_settings: Settings) -> None:
    """The P/A qualifier on the reported value is carried through, not silently dropped (#1602)."""
    readings = nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
    discharge = next(r for r in readings if r.parameter_cd == nwis.DISCHARGE_CFS)
    # The committed Ottawa-at-Lima current reading is flagged provisional.
    assert discharge.qualifiers == ["P"]
    assert discharge.provisional is True


def test_missing_envelope_raises_not_empty(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A payload whose NWIS envelope shifted must raise, not degrade to [] (#1602).

    Returning ``[]`` reads downstream as "gage carrying no data" rather than "connector
    failed" — the exact silent-failure this guards against.
    """
    for drifted in ({}, {"value": None}, {"value": {}}, {"value": {"timeSeries": None}}):
        monkeypatch.setattr(nwis, "cached_get", lambda *a, _p=drifted, **k: _p)
        with pytest.raises(ValueError, match="schema drift"):
            nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)

    # A present-but-empty timeSeries is a legitimate "no matching series" — no raise.
    monkeypatch.setattr(nwis, "cached_get", lambda *a, **k: {"value": {"timeSeries": []}})
    assert nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings) == []


def test_offline_cache_miss_raises(hydro_settings: Settings) -> None:
    with pytest.raises(HydroOfflineError):
        nwis.fetch_streamflow(sites=["00000000"], settings=hydro_settings)


def test_cache_key_is_order_independent() -> None:
    assert cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})


def test_iv_service_uses_short_ttl(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The "right now" IV service must not inherit the week-long slow-moving default (#1365)."""
    assert hydro_settings.nwis_iv_cache_ttl_hours < hydro_settings.hydro_cache_ttl_hours

    seen: dict[str, object] = {}

    def spy(connector: str, params: object, fetch: object, **kw: object) -> object:
        seen["ttl_hours"] = kw.get("ttl_hours")
        return {"value": {"timeSeries": []}}

    monkeypatch.setattr(nwis, "cached_get", spy)
    nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
    assert seen["ttl_hours"] == hydro_settings.nwis_iv_cache_ttl_hours


def test_observed_min_is_derived_not_document(hydro_settings: Settings) -> None:
    # The 7-day-min cross-check, when present, must never masquerade as a 7Q10.
    # (No P7D fixture committed -> offline miss; the point is the source tag, which
    #  we assert directly on a freshly built derived value.)
    from watermark.hydrology.model import ProvenancedValue

    pv = ProvenancedValue.derived(0.4, "cfs", citation="NWIS min P7D (not 7Q10)")
    assert pv.source == "derived"
    assert not pv.verified
