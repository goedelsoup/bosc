"""NWIS connector + the offline cache/fixture machinery (hermetic, no network)."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.connectors import CacheTrace
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
    live = CacheTrace("live", None, 1)
    for drifted in ({}, {"value": None}, {"value": {}}, {"value": {"timeSeries": None}}):
        monkeypatch.setattr(nwis, "cached_get_traced", lambda *a, _p=drifted, **k: (_p, live))
        with pytest.raises(ValueError, match="schema drift"):
            nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)

    # A present-but-empty timeSeries is a legitimate "no matching series" — no raise.
    monkeypatch.setattr(
        nwis, "cached_get_traced", lambda *a, **k: ({"value": {"timeSeries": []}}, live)
    )
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
        return {"value": {"timeSeries": []}}, CacheTrace("live", None, 1)

    monkeypatch.setattr(nwis, "cached_get_traced", spy)
    nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
    assert seen["ttl_hours"] == hydro_settings.nwis_iv_cache_ttl_hours


# --- live-fetch vs offline-fixture provenance (WS-21, #1621) ----------------------------------
# The IV service is "right now" data on a one-hour freshness window, so it is where replaying a
# months-old committed fixture as a current reading does the most damage.


def test_a_replayed_reading_is_dated_and_flagged(hydro_settings: Settings) -> None:
    reading = next(
        r
        for r in nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
        if r.parameter_cd == nwis.DISCHARGE_CFS
    )
    assert reading.retrieved_at is not None
    assert reading.replayed is True
    # NWIS's own observation stamp is the better date, and it is what `asof` prefers.
    assert reading.asof == reading.datetime


def test_a_replayed_reading_never_enters_the_balance_as_a_current_flow(
    hydro_settings: Settings,
) -> None:
    """The headline WS-21 case: an offline replay must not read as the river's flow *now*.

    It stays ``connector``-sourced — a committed fixture is a recorded live pull, so the
    reading really did come off the gage — but it carries the observation's own date and a
    stepped-down confidence, so nothing downstream can treat it as the current condition.
    """
    reading = next(
        r
        for r in nwis.fetch_streamflow(sites=["04187100"], settings=hydro_settings)
        if r.parameter_cd == nwis.DISCHARGE_CFS
    )
    value = reading.as_provenanced("cfs")
    assert value is not None
    assert value.source == "connector"
    assert value.unit == "cfs"  # NWIS spells it ft3/s; the balance's unit is stated, not adopted
    assert value.asof == reading.datetime
    # Provisional (#1602) already floors this reading at `low`; the replay cannot push it
    # below the floor, and must not bounce it back up either.
    assert reading.provisional is True
    assert value.confidence == "low"


def test_the_two_down_weightings_compose_downward() -> None:
    """Approved + replayed lands one step down; provisional + replayed stays at the floor."""
    base = {
        "site_no": "04187100",
        "name": "Ottawa River at Lima",
        "parameter_cd": nwis.DISCHARGE_CFS,
        "value": 36.3,
        "unit": "ft3/s",
        "datetime": "2026-06-06T12:00:00-04:00",
    }
    approved_live = nwis.NwisReading(**base, qualifiers=["A"])
    approved_replayed = nwis.NwisReading(**base, qualifiers=["A"], replayed=True)
    provisional_replayed = nwis.NwisReading(**base, qualifiers=["P"], replayed=True)

    def confidence(reading: nwis.NwisReading) -> str | None:
        value = reading.as_provenanced("cfs")
        return None if value is None else value.confidence

    assert confidence(approved_live) == "high"
    assert confidence(approved_replayed) == "medium"
    assert confidence(provisional_replayed) == "low"


def test_a_reading_with_no_value_yields_no_provenanced_value() -> None:
    empty = nwis.NwisReading(
        site_no="04187100",
        name="Ottawa River at Lima",
        parameter_cd=nwis.DISCHARGE_CFS,
        value=None,
        unit="ft3/s",
        datetime=None,
    )
    assert empty.as_provenanced("cfs") is None


def test_an_undated_reading_falls_back_to_the_retrieval_time() -> None:
    """``None`` reads as "undated" and so, downstream, as "current" — the retrieval time doesn't."""
    reading = nwis.NwisReading(
        site_no="04187100",
        name="Ottawa River at Lima",
        parameter_cd=nwis.DISCHARGE_CFS,
        value=36.3,
        unit="ft3/s",
        datetime=None,
        retrieved_at="2026-06-06T12:00:00+00:00",
    )
    assert reading.asof == "2026-06-06T12:00:00+00:00"


def test_observed_min_is_dated_by_the_observation_it_read(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A "lowest flow in the last 7 days" is a claim about a window, so it states one.

    Replayed undated (as it was before #1621), it read as the current trough. There is no
    committed P7D fixture, so the payload is handed in directly.
    """
    payload = {
        "value": {
            "timeSeries": [
                {
                    "sourceInfo": {
                        "siteName": "Ottawa River at Lima",
                        "siteCode": [{"value": "x"}],
                    },
                    "variable": {
                        "variableCode": [{"value": nwis.DISCHARGE_CFS}],
                        "unit": {"unitCode": "ft3/s"},
                    },
                    "values": [
                        {
                            "value": [
                                {"dateTime": "2026-06-01T00:00:00-04:00", "value": "12.0"},
                                {"dateTime": "2026-06-03T00:00:00-04:00", "value": "4.5"},
                                {"dateTime": "2026-06-05T00:00:00-04:00", "value": "9.1"},
                            ]
                        }
                    ],
                }
            ]
        }
    }
    replayed = CacheTrace("fixture", "2026-06-06T12:00:00+00:00", 1)
    monkeypatch.setattr(nwis, "cached_get_traced", lambda *a, **k: (payload, replayed))

    minimum = nwis.observed_min_discharge("04187100", settings=hydro_settings)
    assert minimum is not None
    assert minimum.value == pytest.approx(4.5)
    assert minimum.asof == "2026-06-03T00:00:00-04:00"  # the trough's own timestamp
    assert minimum.source == "derived"  # still not the regulatory 7Q10


def test_observed_min_is_derived_not_document(hydro_settings: Settings) -> None:
    # The 7-day-min cross-check, when present, must never masquerade as a 7Q10.
    # (No P7D fixture committed -> offline miss; the point is the source tag, which
    #  we assert directly on a freshly built derived value.)
    from watermark.hydrology.model import ProvenancedValue

    pv = ProvenancedValue.derived(0.4, "cfs", citation="NWIS min P7D (not 7Q10)")
    assert pv.source == "derived"
    assert not pv.verified
