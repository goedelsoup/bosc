"""ECHO DMR / effluent-chart connector — fixture-backed (hermetic, no network).

Replays a committed Fort Wayne WWTP (NPDES IN0032191) effluent chart for calendar
2023: the primary outfall's reported monthly flow vs. the 74 MGD design, the CSO
outfall count, and the (empty) exceedance list. None of these may fabricate a value
ECHO didn't send — a no-discharge period stays null, an exceedance appears only where
ECHO reports one.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import echo_dmr
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.units import CFS_TO_MGD
from watermark.models import DmrSeasonality


def _row(
    *,
    value: float | None = 1.0,
    unit: str | None = "MGD",
    stat_base: str | None = "MO AVG",
    stat_base_code: str | None = None,
    std_value: float | None = None,
    std_unit: str | None = None,
) -> echo_dmr.DmrRow:
    """A DmrRow with harmless defaults; override only the fields a test cares about."""
    return echo_dmr.DmrRow(
        period_end="2023-01-31",
        value=value,
        unit=unit,
        std_value=std_value,
        std_unit=std_unit,
        qualifier="=",
        stat_base=stat_base,
        stat_base_code=stat_base_code,
        limit=None,
        limit_type=None,
        exceedance_pct=None,
        nodi=None,
        violations=[],
    )


def test_iso_period_parses_echo_date() -> None:
    assert echo_dmr._iso_period("31-JAN-23") == "2023-01-31"
    assert echo_dmr._iso_period("28-FEB-23") == "2023-02-28"
    assert echo_dmr._iso_period(None) is None
    assert echo_dmr._iso_period("garbage") is None


def test_fetch_fort_wayne_chart_from_fixture(hydro_settings: Settings) -> None:
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    assert chart.npdes_id == "IN0032191"
    assert chart.name == "FORT WAYNE WWTP"
    assert chart.permit_type == "NPDES Individual Permit"
    assert chart.permit_status == "Admin Continued"
    assert chart.major_minor == "M"  # a major discharger
    assert chart.snc_status == "Effluent - Monthly Average Limit"
    # The primary outfall carries 12 monthly flow values; a CSO outfall does not.
    flow_series = chart.series(echo_dmr.FLOW_PARAM)
    assert len(flow_series) >= 1
    primary = next(p for p in flow_series if p.outfall == "001")
    assert sum(1 for r in primary.rows if r.value is not None) == 12
    # Reported values are verbatim — January 2023 monthly-average flow.
    jan = next(r for r in primary.rows if r.period_end == "2023-01-31")
    assert jan.value == pytest.approx(56.016)
    assert jan.unit == "MGD"
    assert jan.stat_base == "MO AVG"


def test_summarize_actual_vs_design(hydro_settings: Settings) -> None:
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=74.0)
    assert summary.primary_outfall == "001"
    assert summary.n_flow_months == 12
    # The 12-month mean of the reported monthly averages — well under the design flow.
    assert summary.actual_flow_mean_mgd == pytest.approx(43.869, abs=0.01)
    assert summary.flow_pct_of_design == pytest.approx(59.3, abs=0.1)
    assert summary.actual_flow_min_mgd == pytest.approx(30.304)
    assert summary.actual_flow_max_mgd == pytest.approx(79.287)
    # 39 permitted overflow (CSO/SSO) outfalls beyond the continuous effluent point; 24 of them
    # actually reported a non-null volume — the rest are permitted-but-inactive (WS-25 / #1625).
    assert summary.overflow_outfalls == 39
    assert summary.active_overflow_outfalls == 24
    # No ECHO-flagged effluent exceedance in the window — an empty list, never "unknown".
    assert summary.exceedances == []


def test_no_design_flow_means_no_percentage(hydro_settings: Settings) -> None:
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    summary = echo_dmr.summarize_discharge(chart)  # design_flow_mgd=None
    assert summary.actual_flow_mean_mgd == pytest.approx(43.869, abs=0.01)
    assert summary.flow_pct_of_design is None


def test_dmr_document_is_regenerable_and_faithful(hydro_settings: Settings) -> None:
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=74.0)
    doc = echo_dmr.dmr_document(chart, summary)
    assert doc["permit"]["npdes_id"] == "IN0032191"
    assert doc["discharge_summary"]["actual_flow_mean_mgd"] == pytest.approx(43.869, abs=0.01)
    assert doc["discharge_summary"]["actual_flow_mean_cfs"] == pytest.approx(67.87, abs=0.1)
    assert doc["discharge_summary"]["design_flow_cfs"] == pytest.approx(114.48, abs=0.1)
    assert len(doc["flow_monthly"]) == 12
    assert doc["exceedances"] == []
    assert "watermark dmr IN0032191" in doc["meta"]["regenerate"]


def test_summarize_ignores_daily_max_rows() -> None:
    # ECHO returns both MO AVG and DAILY MX rows per period. Only MO AVG should
    # enter the mean/min/max/count computation; mixing them inflates all four.
    mo_avg = [
        echo_dmr.DmrRow(
            period_end=f"2023-{m:02d}-01",
            value=float(m),
            unit="MGD",
            qualifier=None,
            stat_base="MO AVG",
            limit=None,
            limit_type=None,
            exceedance_pct=None,
            nodi=None,
            violations=[],
        )
        for m in range(1, 13)  # values 1..12
    ]
    daily_mx = [
        echo_dmr.DmrRow(
            period_end=f"2023-{m:02d}-01",
            value=float(m) * 3,
            unit="MGD",
            qualifier=None,
            stat_base="DAILY MX",
            limit=None,
            limit_type=None,
            exceedance_pct=None,
            nodi=None,
            violations=[],
        )
        for m in range(1, 13)  # values 3..36 — would skew mean if included
    ]
    chart = echo_dmr.EffluentChart(
        npdes_id="TEST001",
        name="Test Plant",
        permit_type=None,
        permit_status=None,
        major_minor=None,
        snc_status=None,
        start_date="2023-01-01",
        end_date="2023-12-31",
        parameters=[
            echo_dmr.DmrParameter(
                outfall="001",
                outfall_type=None,
                parameter_code=echo_dmr.FLOW_PARAM,
                parameter_desc=None,
                monitoring_location=None,
                rows=mo_avg + daily_mx,
            ),
        ],
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=20.0)
    assert summary.n_flow_months == 12  # calendar months, not rows
    assert summary.actual_flow_mean_mgd == pytest.approx(6.5)  # mean(1..12), not mean(1..12, 3..36)
    assert summary.actual_flow_min_mgd == pytest.approx(1.0)  # MO AVG min, not 3.0 (DAILY MX min)
    assert summary.actual_flow_max_mgd == pytest.approx(12.0)  # MO AVG max, not 36.0


def test_pct_to_float_handles_echo_percent_string() -> None:
    # ECHO returns ExceedencePct as a *string with a trailing percent sign* ("13%"),
    # not a bare number. A plain float() choked on the "%" and dropped the exceedance;
    # this parser strips it. A value ECHO didn't report stays None (never fabricated).
    assert echo_dmr._pct_to_float("13%") == pytest.approx(13.0)
    assert echo_dmr._pct_to_float("2%") == pytest.approx(2.0)
    assert echo_dmr._pct_to_float("0.5 %") == pytest.approx(0.5)
    assert echo_dmr._pct_to_float(7) == pytest.approx(7.0)  # tolerate a bare number too
    assert echo_dmr._pct_to_float(None) is None
    assert echo_dmr._pct_to_float("") is None
    assert echo_dmr._pct_to_float("garbage") is None


def test_parse_rows_reads_percent_string_and_violations() -> None:
    # A raw ECHO DMR row: ExceedencePct as "13%" + an NPDESViolations entry. Both are
    # ECHO's own reporting; the parser passes them through verbatim (never computed here).
    rows = echo_dmr._parse_rows(
        [
            {
                "MonitoringPeriodEndDate": "31-JAN-24",
                "DMRValueNmbr": "17",
                "DMRUnitDesc": "mg/L",
                "LimitValueNmbr": "15",
                "LimitValueTypeDesc": "Concentration3",
                "StatisticalBaseShortDesc": "MX WK AV",
                "ExceedencePct": "13%",
                "NPDESViolations": [
                    {
                        "ViolationCode": "E90",
                        "ViolationDesc": "DMR, Limited - Numeric Violation",
                        "ViolationSeverity": "2",
                        "ViolationSeverityDesc": "Non-Reportable Noncompliance Effluent Violation",
                    }
                ],
            }
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.exceedance_pct == pytest.approx(13.0)
    assert len(row.violations) == 1
    assert row.violations[0].code == "E90"
    assert row.violations[0].severity == "2"


def test_summarize_flags_echo_reported_exceedance_with_parameter_context() -> None:
    # A TSS parameter with one ECHO-flagged row (exceedance_pct + violation) and one
    # clean row. Only the flagged row surfaces, carrying which pollutant exceeded where.
    tss = echo_dmr.DmrParameter(
        outfall="001",
        outfall_type="External Outfall",
        parameter_code="00530",
        parameter_desc="Solids, total suspended",
        monitoring_location="Effluent Gross",
        rows=[
            echo_dmr.DmrRow(
                period_end="2024-01-31",
                value=17.0,
                unit="mg/L",
                qualifier="=",
                stat_base="MX WK AV",
                limit=15.0,
                limit_type="Concentration3",
                exceedance_pct=13.0,
                nodi=None,
                violations=[
                    echo_dmr.DmrViolation(
                        code="E90",
                        desc="DMR, Limited - Numeric Violation",
                        severity="2",
                        severity_desc="Non-Reportable Noncompliance Effluent Violation",
                    )
                ],
            ),
            echo_dmr.DmrRow(
                period_end="2024-02-29",
                value=8.0,
                unit="mg/L",
                qualifier="=",
                stat_base="MO AVG",
                limit=10.0,
                limit_type="Concentration2",
                exceedance_pct=None,
                nodi=None,
                violations=[],
            ),
        ],
    )
    chart = echo_dmr.EffluentChart(
        npdes_id="IN0032191",
        name="FORT WAYNE WWTP",
        permit_type=None,
        permit_status=None,
        major_minor="M",
        snc_status="Effluent - Monthly Average Limit",
        start_date="2023-01-01",
        end_date="2026-06-30",
        parameters=[tss],
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=74.0)
    assert len(summary.exceedances) == 1
    exc = summary.exceedances[0]
    assert exc.parameter_desc == "Solids, total suspended"
    assert exc.outfall == "001"
    assert exc.stat_base == "MX WK AV"
    assert exc.value == pytest.approx(17.0)
    assert exc.limit == pytest.approx(15.0)
    assert exc.exceedance_pct == pytest.approx(13.0)
    assert exc.violations[0].code == "E90"
    # The document emitter carries the parameter + violation classification.
    doc = echo_dmr.dmr_document(chart, summary)
    assert doc["discharge_summary"]["reported_exceedances"] == 1
    assert doc["exceedances"][0]["parameter"] == "Solids, total suspended"
    assert doc["exceedances"][0]["violations"][0]["code"] == "E90"


def test_reporting_violation_is_not_an_exceedance() -> None:
    # ECHO's NPDESViolations carries effluent violations (code E…) *and* DMR reporting /
    # non-receipt lapses (code D…, e.g. D80 "Monitor Only - Overdue"). Only an effluent
    # over-limit is a receiving-water exceedance; a paperwork lapse must never inflate the list.
    assert echo_dmr._is_effluent_violation(
        echo_dmr.DmrViolation(code="E90", desc=None, severity=None, severity_desc=None)
    )
    assert not echo_dmr._is_effluent_violation(
        echo_dmr.DmrViolation(code="D80", desc=None, severity=None, severity_desc=None)
    )
    param = echo_dmr.DmrParameter(
        outfall="581",
        outfall_type=None,
        parameter_code="51129",
        parameter_desc="Biosolids weight",
        monitoring_location=None,
        rows=[
            echo_dmr.DmrRow(
                period_end="2023-03-31",
                value=None,
                unit=None,
                qualifier=None,
                stat_base="MO AVG",
                limit=None,
                limit_type=None,
                exceedance_pct=None,  # a reporting lapse carries no over-limit percentage
                nodi=None,
                violations=[
                    echo_dmr.DmrViolation(
                        code="D80",
                        desc="DMR, Monitor Only - Overdue",
                        severity="1",
                        severity_desc="DMR Non-Receipt Reporting Violation",
                    )
                ],
            )
        ],
    )
    chart = echo_dmr.EffluentChart(
        npdes_id="OH0027421",
        name="Sidney WWTP",
        permit_type=None,
        permit_status=None,
        major_minor=None,
        snc_status=None,
        start_date="2023-01-01",
        end_date="2023-12-31",
        parameters=[param],
    )
    summary = echo_dmr.summarize_discharge(chart)
    assert summary.exceedances == []  # the D80 overdue report is not an effluent exceedance


def test_offline_cache_miss_raises(hydro_settings: Settings) -> None:
    # A permit with no committed fixture -> offline miss must be loud, not silent.
    with pytest.raises(HydroOfflineError):
        echo_dmr.fetch_effluent_chart(
            "XX9999999", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
        )


def test_is_monthly_avg_robust_to_stat_base_representation() -> None:
    # The #1601 fix: don't rely on an exact "MO AVG" string. The stable ICIS
    # StatisticalBaseCode ("MK") wins when present, whatever the descriptor reads.
    assert echo_dmr._is_monthly_avg(_row(stat_base_code="MK", stat_base="Monthly Average"))
    assert echo_dmr._is_monthly_avg(_row(stat_base_code="mk", stat_base=None))
    assert not echo_dmr._is_monthly_avg(_row(stat_base_code="DD", stat_base="MO AVG"))
    # With no code, accept the short OR the long descriptor, case-insensitively — the exact
    # "MO AVG" match this replaces silently zeroed flow when ECHO sent only "Monthly Average".
    assert echo_dmr._is_monthly_avg(_row(stat_base_code=None, stat_base="MO AVG"))
    assert echo_dmr._is_monthly_avg(_row(stat_base_code=None, stat_base="Monthly Average"))
    assert echo_dmr._is_monthly_avg(_row(stat_base_code=None, stat_base="monthly avg"))
    assert not echo_dmr._is_monthly_avg(_row(stat_base_code=None, stat_base="DAILY MX"))
    assert not echo_dmr._is_monthly_avg(_row(stat_base_code=None, stat_base=None))


def test_flow_mgd_converts_reported_unit() -> None:
    # ECHO's 50050 is usually — but not always — MGD, so the value is converted by its
    # reported unit rather than assumed MGD (#1601).
    assert echo_dmr._flow_mgd(_row(value=12.0, unit="MGD")) == pytest.approx(12.0)
    assert echo_dmr._flow_mgd(_row(value=3_000_000.0, unit="GPD")) == pytest.approx(3.0)
    assert echo_dmr._flow_mgd(_row(value=2.0, unit="CFS")) == pytest.approx(2.0 * CFS_TO_MGD)
    # ECHO's own standardized value is preferred when it standardized to MGD.
    row = _row(value=99.0, unit=None, std_value=9.38, std_unit="MGD")
    assert echo_dmr._flow_mgd(row) == pytest.approx(9.38)
    # No unit signal at all -> the historical MGD assumption (50050 is a flow), kept only then.
    assert echo_dmr._flow_mgd(_row(value=4.0, unit=None)) == pytest.approx(4.0)
    # A present-but-unrecognized unit is NOT silently averaged as MGD -> dropped.
    assert echo_dmr._flow_mgd(_row(value=17.0, unit="mg/L")) is None
    assert echo_dmr._flow_mgd(_row(value=None, unit="MGD")) is None


def test_stat_base_and_unit_read_from_dual_field_fixture(hydro_settings: Settings) -> None:
    """A permit whose flow ECHO reports in GPD with the stat base given as only the long
    "Monthly Average" descriptor (+ the "MK" code) — the dual short/long fragility (#1601).

    The old exact-"MO AVG" match would have collapsed the series to zero, and the assume-MGD
    reduction would have mislabeled the raw GPD figure as MGD; the robust stat match plus
    unit conversion recover the true 12-month MGD mean.
    """
    chart = echo_dmr.fetch_effluent_chart(
        "OH0091234", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    prim = next(p for p in chart.series(echo_dmr.FLOW_PARAM) if p.outfall == "001")
    jan = next(r for r in prim.rows if r.period_end == "2023-01-31" and echo_dmr._is_monthly_avg(r))
    assert jan.unit == "GPD"  # reported in gallons/day, not MGD
    assert jan.stat_base == "Monthly Average"  # only the long descriptor — no "MO AVG"
    assert jan.stat_base_code == "MK"
    assert jan.value == pytest.approx(2_000_000.0)  # verbatim GPD, never rewritten

    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=5.0)
    assert summary.primary_outfall == "001"
    assert summary.n_flow_months == 12  # robust match found all 12 monthly rows, not 0
    assert summary.actual_flow_mean_mgd == pytest.approx(2.983, abs=0.001)  # GPD reduced to MGD
    assert summary.actual_flow_min_mgd == pytest.approx(2.0)
    assert summary.actual_flow_max_mgd == pytest.approx(4.0)  # not a daily-max (DD) row
    assert summary.flow_pct_of_design == pytest.approx(59.7, abs=0.1)

    doc = echo_dmr.dmr_document(chart, summary)
    assert doc["discharge_summary"]["actual_flow_mean_mgd"] == pytest.approx(2.983, abs=0.001)
    # The document's monthly series is in MGD, not the raw GPD figure.
    jan_doc = next(
        s
        for s in doc["flow_monthly"]
        if s["period_end"] == "2023-01-31" and s["stat_base"] == "Monthly Average"
    )
    assert jan_doc["value_mgd"] == pytest.approx(2.0)


def test_summarize_drops_flow_row_with_unconvertible_unit() -> None:
    # A monthly-average flow row ECHO reported in a non-flow unit must NOT be averaged as MGD
    # (the silent-wrong-number the #1601 fix prevents): it is dropped, so the mean is over the
    # two convertible rows only, never inflated by the raw 999 figure.
    param = echo_dmr.DmrParameter(
        outfall="001",
        outfall_type="External Outfall",
        parameter_code=echo_dmr.FLOW_PARAM,
        parameter_desc="Flow",
        monitoring_location="Effluent Gross",
        rows=[
            _row(value=2.0, unit="MGD", stat_base="MO AVG"),
            _row(value=4.0, unit="MGD", stat_base="MO AVG"),
            _row(value=999.0, unit="mg/L", stat_base="MO AVG"),  # bogus unit -> dropped
        ],
    )
    chart = echo_dmr.EffluentChart(
        npdes_id="TEST002",
        name="Unit Test Plant",
        permit_type=None,
        permit_status=None,
        major_minor=None,
        snc_status=None,
        start_date="2023-01-01",
        end_date="2023-12-31",
        parameters=[param],
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=10.0)
    assert summary.n_flow_months == 2  # the mg/L row is excluded, not counted
    assert summary.actual_flow_mean_mgd == pytest.approx(3.0)  # mean(2, 4), not (2+4+999)/3
    assert summary.actual_flow_max_mgd == pytest.approx(4.0)  # 999 never enters the series


def _flow_param(
    values_by_period: dict[str, float], *, stat_base: str = "MO AVG"
) -> echo_dmr.DmrParameter:
    """A flow (50050) outfall with one monthly-average row per (period_end -> MGD) entry."""
    return echo_dmr.DmrParameter(
        outfall="001",
        outfall_type="External Outfall",
        parameter_code=echo_dmr.FLOW_PARAM,
        parameter_desc="Flow",
        monitoring_location="Effluent Gross",
        rows=[
            echo_dmr.DmrRow(
                period_end=period,
                value=value,
                unit="MGD",
                qualifier="=",
                stat_base=stat_base,
                limit=None,
                limit_type=None,
                exceedance_pct=None,
                nodi=None,
                violations=[],
            )
            for period, value in values_by_period.items()
        ],
    )


def test_seasonality_flags_summer_peak() -> None:
    # A temperature-driven evaporative signature: warm months (May-Oct) discharge ~5x the cool
    # months. warm_ratio well above 1 and a high CV — the shape an evaporative tower's blowdown
    # makes and a dry loop does not.
    warm = {f"2023-{m:02d}-28": 10.0 for m in (5, 6, 7, 8, 9, 10)}
    cool = {f"2023-{m:02d}-28": 2.0 for m in (1, 2, 3, 4, 11, 12)}
    s = echo_dmr.flow_seasonality(_flow_param({**cool, **warm}))
    assert s is not None
    assert s.n_months == 12
    assert s.warm_months == [5, 6, 7, 8, 9, 10]
    assert s.warm_mean_mgd == pytest.approx(10.0)
    assert s.cool_mean_mgd == pytest.approx(2.0)
    assert s.warm_ratio == pytest.approx(5.0)
    assert s.peak_month in {5, 6, 7, 8, 9, 10}
    assert s.peak_mean_mgd == pytest.approx(10.0)
    assert s.cv is not None and s.cv > 0.5


def test_seasonality_flat_loop_has_ratio_near_one_and_zero_cv() -> None:
    # A genuinely flat discharge (a dry/sealed loop reads this way): every month equal.
    s = echo_dmr.flow_seasonality(_flow_param({f"2023-{m:02d}-28": 4.0 for m in range(1, 13)}))
    assert s is not None
    assert s.warm_ratio == pytest.approx(1.0)
    assert s.cv == pytest.approx(0.0)
    assert s.warm_mean_mgd == pytest.approx(4.0)
    assert s.cool_mean_mgd == pytest.approx(4.0)


def test_seasonality_single_season_has_no_ratio() -> None:
    # Only warm-month observations -> a warm/cool ratio is undefined (never fabricated), but the
    # per-month CV can still be computed across the months present.
    s = echo_dmr.flow_seasonality(_flow_param({f"2023-{m:02d}-28": float(m) for m in (6, 7, 8)}))
    assert s is not None
    assert s.n_months == 3
    assert s.warm_ratio is None  # no cool-month observation
    assert s.cool_mean_mgd is None
    assert s.warm_mean_mgd == pytest.approx(7.0)  # mean(6, 7, 8)
    assert s.cv is not None  # >= 2 distinct months


def test_seasonality_folds_multiple_years_by_calendar_month() -> None:
    # Two Januarys average into one calendar-month mean; a multi-year window is not double-counted.
    param = _flow_param({"2023-01-31": 4.0, "2024-01-31": 6.0, "2023-07-31": 10.0})
    s = echo_dmr.flow_seasonality(param)
    assert s is not None
    assert s.n_months == 2  # January and July, not three rows
    assert s.peak_month == 7
    # January folds to mean(4, 6) = 5; that is the cool-month mean.
    assert s.cool_mean_mgd == pytest.approx(5.0)


def test_seasonality_weights_each_calendar_month_equally_under_uneven_coverage() -> None:
    # A month reported in more years must NOT dominate the season mean: warm/cool means are taken
    # over the folded per-calendar-month means, so July (3 obs) and August (1 obs) count once each.
    param = _flow_param(
        {
            "2023-07-31": 12.0,  # July, three obs across years -> month-mean 12
            "2024-07-31": 12.0,
            "2025-07-31": 12.0,
            "2023-08-31": 6.0,  # August, one obs -> month-mean 6
            "2023-01-31": 3.0,  # January (cool), one obs -> month-mean 3
        }
    )
    s = echo_dmr.flow_seasonality(param)
    assert s is not None
    assert s.n_months == 3
    # Folded: mean(12, 6) = 9.0 — NOT the raw-pooled (12+12+12+6)/4 = 10.5.
    assert s.warm_mean_mgd == pytest.approx(9.0)
    assert s.cool_mean_mgd == pytest.approx(3.0)
    assert s.warm_ratio == pytest.approx(3.0)  # 9/3, not the pooled 10.5/3 = 3.5


def test_seasonality_carries_derived_provenance() -> None:
    # Every present seasonality object is tagged: a `derived`, medium-confidence [inference] shape
    # over the reported flow, with `asof` = the latest period covered.
    param = _flow_param({f"2023-{m:02d}-28": float(m) for m in range(1, 13)})
    s = echo_dmr.flow_seasonality(param)
    assert s is not None
    assert s.source == "derived"
    assert s.confidence == "medium"
    assert s.citation is not None and "50050" in s.citation
    assert s.asof == "2023-12-28"  # the latest month the series covers


def test_seasonality_ignores_daily_max_and_unconvertible_rows() -> None:
    # Only monthly-average, unit-reducible rows enter the shape — a DAILY MX row must not skew it.
    param = _flow_param({f"2023-{m:02d}-28": 3.0 for m in range(1, 13)})
    param.rows.append(
        echo_dmr.DmrRow(
            period_end="2023-07-31",
            value=99.0,
            unit="MGD",
            qualifier="=",
            stat_base="DAILY MX",  # excluded
            limit=None,
            limit_type=None,
            exceedance_pct=None,
            nodi=None,
            violations=[],
        )
    )
    s = echo_dmr.flow_seasonality(param)
    assert s is not None
    assert s.warm_ratio == pytest.approx(1.0)  # the 99 DAILY MX row never enters
    assert s.peak_mean_mgd == pytest.approx(3.0)


def test_seasonality_none_for_missing_or_empty_series() -> None:
    assert echo_dmr.flow_seasonality(None) is None
    assert echo_dmr.flow_seasonality(_flow_param({})) is None


def test_seasonality_custom_warm_window() -> None:
    # A3 / a site can override the warm window; the ratio recomputes against it.
    param = _flow_param({f"2023-{m:02d}-28": (10.0 if m in (7, 8) else 2.0) for m in range(1, 13)})
    s = echo_dmr.flow_seasonality(param, warm_months=frozenset({7, 8}))
    assert s is not None
    assert s.warm_months == [7, 8]
    assert s.warm_mean_mgd == pytest.approx(10.0)
    assert s.warm_ratio == pytest.approx(5.0)


def test_summarize_and_document_carry_seasonality(hydro_settings: Settings) -> None:
    # The Fort Wayne WWTP fixture: a POTW's flow peaks in spring (wet-weather I&I), NOT summer —
    # warm_ratio below 1, the *opposite* of an evaporative cooling signature. The summary and the
    # regenerable document both carry the block, with a human-readable peak-month name.
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=74.0)
    assert summary.seasonality is not None
    assert summary.seasonality.warm_ratio is not None and summary.seasonality.warm_ratio < 1.0
    doc = echo_dmr.dmr_document(chart, summary)
    assert doc["seasonality"]["warm_ratio"] == pytest.approx(summary.seasonality.warm_ratio)
    assert doc["seasonality"]["peak_month_name"] is not None
    assert "[inference]" in doc["seasonality"]["discipline"]
    # The document carries the provenance quad, and validates back into the DmrSeasonality model.
    assert doc["seasonality"]["source"] == "derived"
    assert doc["seasonality"]["confidence"] == "medium"
    assert doc["seasonality"]["asof"] == "2023-12-31"
    DmrSeasonality.model_validate(doc["seasonality"])


def test_lima_wwtp_reports_effluent_exceedances(hydro_settings: Settings) -> None:
    """The City of Lima WWTP (OH0026069, #1536) — flow vs the 18.5 MGD design, and a
    real ECHO-flagged exceedance (mercury), the non-empty case the Fort Wayne fixture
    (an empty exceedance list) doesn't cover. Fixture is a curated 2023 subset of the
    live pull (outfall 001 flow + mercury + the five CSO markers); values are verbatim.
    """
    chart = echo_dmr.fetch_effluent_chart(
        "OH0026069", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    assert chart.name == "LIMA WWTP"
    assert chart.permit_status == "Effective"
    assert chart.major_minor == "M"  # a major discharger

    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=18.5)
    assert summary.primary_outfall == "001"
    assert summary.n_flow_months == 12
    # Reported actuals run well under the permitted design flow.
    assert summary.actual_flow_mean_mgd == pytest.approx(13.106, abs=0.01)
    assert summary.actual_flow_max_mgd == pytest.approx(19.671)
    assert summary.flow_pct_of_design == pytest.approx(70.8, abs=0.1)
    # 5 permitted overflow (CSO/SSO) outfalls, but NONE reported a non-null volume in the window —
    # the old `cso_outfalls` count would overstate the active overflow points (WS-25 / #1625).
    assert summary.overflow_outfalls == 5
    assert summary.active_overflow_outfalls == 0

    # The non-empty exceedance path: ECHO's own E90 flag on the mercury monthly average,
    # parsed verbatim (value/limit/percent), never computed by comparing value to limit.
    assert len(summary.exceedances) == 1
    hg = summary.exceedances[0]
    assert hg.period_end == "2023-08-31"
    assert hg.parameter_desc is not None and "Mercury" in hg.parameter_desc
    assert hg.value == pytest.approx(6.67)
    assert hg.limit == pytest.approx(3.5)
    assert hg.exceedance_pct == pytest.approx(91.0)
    assert [v.code for v in hg.violations] == ["E90"]


# --- Effluent temperature (#1718, thermal-discharge validation) -------------------------------
def _temp_row(
    *,
    value: float | None,
    period_end: str = "2024-07-31",
    stat_base_code: str = "DD",
    unit: str | None = None,
    std_unit: str | None = "deg F",
    limit: float | None = None,
    limit_unit: str | None = None,
) -> echo_dmr.DmrRow:
    """A temperature DmrRow shaped like ECHO's (value mirrored into DMRValueStdUnits)."""
    return echo_dmr.DmrRow(
        period_end=period_end,
        value=value,
        unit=unit,
        std_value=value,
        std_unit=std_unit,
        qualifier=None,
        stat_base=None,
        stat_base_code=stat_base_code,
        limit=limit,
        limit_type=None,
        limit_unit=limit_unit,
        exceedance_pct=None,
        nodi=None if value is not None else "C",
        violations=[],
    )


def _temp_param(
    rows: list[echo_dmr.DmrRow],
    *,
    outfall: str = "001",
    code: str = echo_dmr.TEMP_PARAM_F,
    location: str | None = "Effluent Gross",
) -> echo_dmr.DmrParameter:
    return echo_dmr.DmrParameter(
        outfall=outfall,
        outfall_type="External Outfall",
        parameter_code=code,
        parameter_desc="Temperature, water",
        monitoring_location=location,
        rows=rows,
    )


def test_temperature_converts_by_reported_unit_not_by_assumption() -> None:
    """00011 is Fahrenheit and 00010 Celsius — a screen that assumed one would be ~18 degC out."""
    assert echo_dmr._temp_c(_temp_row(value=86.0), echo_dmr.TEMP_PARAM_F) == pytest.approx(30.0)
    celsius = _temp_row(value=25.4, std_unit="deg C")
    assert echo_dmr._temp_c(celsius, echo_dmr.TEMP_PARAM_C) == pytest.approx(25.4)
    # A present-but-unrecognized unit is DROPPED, never read as if it were already Celsius.
    assert echo_dmr._temp_c(_temp_row(value=86.0, std_unit="kelvin"), echo_dmr.TEMP_PARAM_F) is None
    # No unit signal at all: the parameter code's definitional unit stands in.
    bare = _temp_row(value=86.0, std_unit=None, unit=None)
    assert echo_dmr._temp_c(bare, echo_dmr.TEMP_PARAM_F) == pytest.approx(30.0)
    assert echo_dmr._temp_c(bare, echo_dmr.TEMP_PARAM_C) == pytest.approx(86.0)


def test_temperature_series_separates_daily_max_from_monthly_average() -> None:
    """Ohio's criterion is a DAILY MAXIMUM, so the two stat bases must not be pooled."""
    series = echo_dmr.temperature_series(
        _temp_param(
            [
                _temp_row(value=90.0, stat_base_code="DD", period_end="2024-08-31"),
                _temp_row(value=86.0, stat_base_code="MK", period_end="2024-08-31"),
                _temp_row(value=82.0, stat_base_code="DD", period_end="2024-09-30"),
                _temp_row(value=78.0, stat_base_code="MK", period_end="2024-09-30"),
            ]
        )
    )
    assert series is not None
    assert series.n_obs == 4
    assert series.peak_daily_max_c == pytest.approx(32.22, abs=0.01)  # 90 degF
    assert series.peak_daily_max_period == "2024-08-31"
    assert series.peak_monthly_avg_c == pytest.approx(30.0, abs=0.01)  # 86 degF
    assert series.instream is False
    assert series.monitor_only is True  # no numeric limit on any row


def test_temperature_series_reports_the_warm_season_limit_ceiling() -> None:
    """An Ohio thermal limit is seasonal; the warm-season ceiling is what binds at design."""
    series = echo_dmr.temperature_series(
        _temp_param(
            [
                _temp_row(value=None, limit=72.0, limit_unit="deg F", period_end="2024-05-31"),
                _temp_row(value=None, limit=85.0, limit_unit="deg F", period_end="2024-07-31"),
            ]
        )
    )
    assert series is not None
    assert series.limit_daily_max_c == pytest.approx(29.44, abs=0.01)  # 85 degF, not the 72
    assert series.limit_seasonal is True
    assert series.monitor_only is False
    assert series.n_obs == 0  # monitored, nothing reported — distinct from "not monitored"


def test_temperature_series_marks_an_instream_station() -> None:
    series = echo_dmr.temperature_series(
        _temp_param(
            [_temp_row(value=24.0, std_unit="deg C")],
            outfall="901",
            code=echo_dmr.TEMP_PARAM_C,
            location="Downstream Monitoring",
        )
    )
    assert series is not None and series.instream is True


def test_temperature_series_ignores_a_non_temperature_parameter() -> None:
    flow = _flow_param({"2024-07-31": 3.6})
    assert echo_dmr.temperature_series(flow) is None


def test_thermal_record_pairs_each_outfall_with_its_own_flow(hydro_settings: Settings) -> None:
    """The Lima Refinery (OH0002623) — the Ottawa corridor's warmest reported discharger.

    Reports temperature under 00011 (degF) at 11 outfalls; outfall 001 is the warmest and the
    one that actually flows. The heat load needs the SAME outfall's flow, never a plant-wide one.
    """
    record = echo_dmr.fetch_thermal_record(
        "OH0002623", start_date="2024-05-01", end_date="2024-10-31", settings=hydro_settings
    )
    assert record.name == "LIMA REFINERY"
    assert record.instream == []  # no upstream/downstream temperature station on this permit
    primary = record.primary_effluent
    assert primary is not None
    assert primary.outfall == "001"
    assert primary.temperature.parameter_code == echo_dmr.TEMP_PARAM_F
    assert primary.temperature.reported_unit == "deg F"
    assert primary.temperature.peak_daily_max_c == pytest.approx(32.22, abs=0.01)  # 90 degF
    assert primary.flow_mean_mgd == pytest.approx(3.7, abs=0.01)
    # The numeric thermal limit sits on a DIFFERENT outfall (003) than the one that discharges;
    # 001 itself is monitor-only, which is the finding the screen surfaces.
    assert primary.temperature.monitor_only is True
    limited = {o.outfall for o in record.effluent if o.temperature.limit_daily_max_c is not None}
    assert limited == {"003"}


def test_thermal_record_reads_the_celsius_permit_and_its_instream_station(
    hydro_settings: Settings,
) -> None:
    """Lima's WWTP (OH0026069) reports 00010 (degC) AND a downstream river station — the
    observed receiving-water temperature the thermal screen's design ambient reads off."""
    record = echo_dmr.fetch_thermal_record(
        "OH0026069", start_date="2024-05-01", end_date="2024-10-31", settings=hydro_settings
    )
    primary = record.primary_effluent
    assert primary is not None and primary.outfall == "001"
    assert primary.temperature.parameter_code == echo_dmr.TEMP_PARAM_C
    assert primary.temperature.peak_daily_max_c == pytest.approx(25.4, abs=0.01)
    assert primary.flow_mean_mgd == pytest.approx(12.77, abs=0.01)
    instream = record.warmest_instream
    assert instream is not None
    assert instream.outfall == "901"
    assert instream.instream is True
    assert instream.temperature.peak_daily_max_c == pytest.approx(24.0, abs=0.01)


def test_thermal_record_is_empty_for_a_permit_that_reports_no_temperature(
    hydro_settings: Settings,
) -> None:
    """A cited absence: the permit exists and answers, and reports no temperature at all."""
    record = echo_dmr.fetch_thermal_record(
        "OHGC02549", start_date="2024-05-01", end_date="2024-10-31", settings=hydro_settings
    )
    assert record.name == "JOINT SYSTEMS MANUFACTURING CENTER"
    assert record.outfalls == []
    assert record.primary_effluent is None


def test_thermal_record_keeps_a_monitored_but_unreported_outfall(hydro_settings: Settings) -> None:
    """Superior Forge (OH0095346) monitors temperature and reported no value in the window —
    'monitored, nothing reported' is a different finding from 'not monitored'."""
    record = echo_dmr.fetch_thermal_record(
        "OH0095346", start_date="2024-05-01", end_date="2024-10-31", settings=hydro_settings
    )
    assert [o.outfall for o in record.outfalls] == ["001"]
    assert record.outfalls[0].temperature.n_obs == 0
    assert record.primary_effluent is None  # nothing reported -> nothing to screen


def test_parameter_filter_keeps_the_unfiltered_cache_key_stable(hydro_settings: Settings) -> None:
    """Adding the ECHO parameter filter must not re-key the existing whole-chart fixtures."""
    from watermark.hydrology.connectors._cache import cache_key

    unfiltered = cache_key(
        {
            "_service": "get_effluent_chart",
            "output": "JSON",
            "p_id": "IN0032191",
            "start_date": "01/01/2023",
            "end_date": "12/31/2023",
        }
    )
    chart = echo_dmr.fetch_effluent_chart(
        "IN0032191", start_date="2023-01-01", end_date="2023-12-31", settings=hydro_settings
    )
    assert chart.npdes_id == "IN0032191"  # replayed from the pre-existing fixture
    assert (hydro_settings.hydro_fixtures_dir / "echo_dmr" / f"{unfiltered}.json").is_file()


def test_a_value_under_an_unscreened_statistic_is_counted_but_not_screened() -> None:
    """ "Reported under a statistic we don't read" must stay distinguishable from "not reported".

    Ohio's criterion is a daily maximum, so only the DD/MK rows can be screened against it —
    but folding a reported weekly average into `n_obs == 0` would make data that IS on the
    record read as absent.
    """
    series = echo_dmr.temperature_series(
        _temp_param(
            [
                _temp_row(value=88.0, stat_base_code="WA"),  # weekly average — not screened
                _temp_row(value=84.0, stat_base_code="DB"),  # daily minimum — not screened
            ]
        )
    )
    assert series is not None
    assert series.n_obs == 2  # both are on the record
    assert series.n_unscreened_obs == 2
    assert series.peak_daily_max_c is None and series.mean_monthly_avg_c is None
    assert series.screenable is False  # nothing a daily-maximum criterion can be read against


def test_screenable_not_n_obs_selects_the_outfall_to_screen() -> None:
    """An outfall whose only values are unscreened must not become the primary effluent."""
    record = echo_dmr.thermal_record(
        echo_dmr.EffluentChart(
            npdes_id="OH9999999",
            name="TEST",
            permit_type=None,
            permit_status=None,
            major_minor=None,
            snc_status=None,
            start_date="2024-05-01",
            end_date="2024-10-31",
            parameters=[
                _temp_param([_temp_row(value=88.0, stat_base_code="WA")], outfall="001"),
                _temp_param([_temp_row(value=90.0, stat_base_code="DD")], outfall="002"),
            ],
        )
    )
    assert {o.outfall for o in record.outfalls} == {"001", "002"}
    primary = record.primary_effluent
    assert primary is not None and primary.outfall == "002"  # not 001, despite both having n_obs
