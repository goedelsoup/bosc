"""EIA-930 balancing-authority interchange connector + the campus comparison (#95).

The "interchange layer" of epic #93: pull the BA's hourly demand / net generation /
total net interchange from the EIA-930 Hourly Electric Grid Monitor (api.eia.gov,
region-data route), **reduce to a small set of window aggregates inside the fetch**
(like the QCEW connector reduces its CSV) so the cached payload / committed fixture
stays tiny, and situate the campus load against it: does the added ~275-348 MW come
from in-BA generation or net imports?

Connector contract: pure ``fn(..., settings) -> pydantic`` through the shared
``cached_get`` (econ cache/offline/fixtures, shared with #91/#94); keyed via
``WATERMARK_EIA_API_KEY`` (excluded from the cache key); a committed fixture under
``tests/fixtures/economics/eia930/`` keeps tests hermetic. Fields are selected **by
name** (``type`` / ``value`` / ``period``), never by index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import yaml

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get
from watermark.facility.power import derive_power_basis
from watermark.grid.model import BAInterchange, CampusInterchangeComparison
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# EIA-930 region-data interchange types: Demand, Net Generation, Total Interchange.
_TYPES = ("D", "NG", "TI")
# A representative recent window (a summer month — peak cooling demand, data-center
# relevant). Fixed so the cache key is deterministic and the committed fixture matches.
_DEFAULT_START = "2024-06-01"
_DEFAULT_END = "2024-06-30"


class Eia930Error(RuntimeError):
    """The EIA-930 API returned an unusable response (most often a missing/invalid key)."""


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _reduce_region_data(
    rows: list[dict[str, Any]], ba: str, start: str, end: str
) -> dict[str, Any]:
    """Reduce EIA-930 region-data rows to per-type window aggregates (small payload)."""
    by_type: dict[str, list[float]] = {t: [] for t in _TYPES}
    for r in rows:
        t, v = r.get("type"), r.get("value")
        if t in by_type and v is not None:
            try:
                by_type[t].append(float(v))
            except (TypeError, ValueError):
                continue
    d, ng, ti = by_type["D"], by_type["NG"], by_type["TI"]
    # An empty response (a wrong BA code, or an HTTP-200 hiccup with an empty data[]) must not
    # become a zero-filled interchange model — the comparison needs all three series, so refuse
    # rather than fabricate demand=netgen=interchange=0 (A2/#1638; mirrors the LMP _reduce guard).
    if not d or not ng or not ti:
        missing = ", ".join(t for t, xs in (("D", d), ("NG", ng), ("TI", ti)) if not xs)
        raise Eia930Error(
            f"EIA-930 region-data for {ba} {start}..{end} returned no rows for [{missing}] — "
            "refusing to build a zero-filled interchange model (wrong BA code or empty response)"
        )
    return {
        "ba": ba,
        "start": start,
        "end": end,
        "hours": len(d),
        "demand_mean": _mean(d),
        "demand_peak": max(d) if d else 0.0,
        "netgen_mean": _mean(ng),
        "ti_mean": _mean(ti),
        "ti_min": min(ti) if ti else 0.0,
        "ti_max": max(ti) if ti else 0.0,
        "import_hours": sum(1 for x in ti if x < 0),
    }


def fetch_ba_interchange(
    *,
    ba: str = "PJM",
    start: str = _DEFAULT_START,
    end: str = _DEFAULT_END,
    settings: Settings | None = None,
) -> BAInterchange:
    """One BA's EIA-930 hourly D/NG/TI reduced to window aggregates (cached)."""
    settings = settings or get_settings()
    params = {"connector": "eia930", "route": "region-data", "ba": ba, "start": start, "end": end}

    def fetch() -> Any:
        # httpx accepts a list of (key, value) tuples for repeated query keys
        # (facets[type][] appears once per type); typed to its param-value union.
        query: list[tuple[str, str | int | float | bool | None]] = [
            ("frequency", "hourly"),
            ("data[0]", "value"),
            ("facets[respondent][]", ba),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("length", "5000"),
        ]
        query += [("facets[type][]", t) for t in _TYPES]
        if settings.eia_api_key:
            query.append(("api_key", settings.eia_api_key))
        resp = httpx.get(
            f"{settings.eia_base_url}/electricity/rto/region-data/data",
            params=query,
            timeout=settings.econ_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            hint = "invalid WATERMARK_EIA_API_KEY" if settings.eia_api_key else "no key set"
            raise Eia930Error(f"EIA-930 returned non-JSON ({hint}): {resp.text[:60]!r}") from exc
        rows = (((body or {}).get("response") or {}).get("data")) or []
        return _reduce_region_data(rows, ba, start, end)

    payload = cast(
        "dict[str, Any]",
        cached_get(
            "eia930",
            params,
            fetch,
            cache_dir=settings.econ_cache_dir,
            offline=settings.econ_offline,
            fixtures_dir=settings.econ_fixtures_dir,
        ),
    )
    hours = int(payload["hours"])
    if hours <= 0:
        # Defends the offline path too: a committed fixture that reduced to zero rows must
        # raise on read, not silently produce a zeros model (A2/#1638).
        raise Eia930Error(
            f"EIA-930 region-data payload for {ba} {start}..{end} has no hours — empty/poisoned "
            "response; refusing to build a zero-filled interchange model"
        )
    cite = f"EIA-930 region-data {ba} {start}..{end} ({hours} h)"
    import_frac = payload["import_hours"] / hours if hours else 0.0
    # The window's last day is how current these aggregates are (G1/#1644) — the same #1107
    # marker the NWIS reads carry. The window is deliberately fixed (cache determinism), which
    # is exactly why it has to be dated: nothing else about a re-run would reveal its age.
    asof = end
    return BAInterchange(
        ba=ba,
        period_start=start,
        period_end=end,
        hours=hours,
        demand_mean_mw=ProvenancedValue.from_connector(
            round(float(payload["demand_mean"])), "MW", citation=cite, asof=asof
        ),
        demand_peak_mw=ProvenancedValue.from_connector(
            round(float(payload["demand_peak"])), "MW", citation=cite, asof=asof
        ),
        net_generation_mean_mw=ProvenancedValue.from_connector(
            round(float(payload["netgen_mean"])), "MW", citation=cite, asof=asof
        ),
        total_interchange_mean_mw=ProvenancedValue.from_connector(
            round(float(payload["ti_mean"])),
            "MW",
            citation=f"{cite}; + exports / - imports",
            asof=asof,
        ),
        interchange_min_mw=ProvenancedValue.from_connector(
            round(float(payload["ti_min"])),
            "MW",
            citation=f"{cite}; most-importing hour",
            asof=asof,
        ),
        interchange_max_mw=ProvenancedValue.from_connector(
            round(float(payload["ti_max"])),
            "MW",
            citation=f"{cite}; most-exporting hour",
            asof=asof,
        ),
        net_import_hours_fraction=ProvenancedValue.derived(
            round(import_frac, 3),
            "fraction",
            citation=f"{payload['import_hours']}/{hours} hours with net imports (TI < 0)",
        ),
        note=(
            "EIA-930 hourly D/NG/TI reduced to window means; sign convention + = net "
            "exports, - = net imports. A representative window, not the full year."
        ),
    )


def fetch_ba_annual_load(
    *, ba: str = "PJM", year: int | None = None, settings: Settings | None = None
) -> ProvenancedValue:
    """The BA's total annual demand (GWh) from EIA-930 daily demand, summed (cached).

    Uses the ``daily-region-data`` route filtered to the **Eastern** timezone: the daily
    route reports each day under five timezone conventions (Arizona/Central/Eastern/
    Mountain/Pacific), so without the filter every day is counted 5x. 365-366 daily MWh
    demand values are summed to the annual total inside the fetch (tiny cached payload).

    ``year`` defaults to ``settings.eia930_year`` rather than a literal in this signature
    (G2/#1644). This figure is one of three load-share denominators, each on its own
    publication schedule; a vintage that only exists as a call-site default is one nobody
    finds when the others move ahead of it.
    """
    settings = settings or get_settings()
    year = year if year is not None else settings.eia930_year
    params = {
        "connector": "eia930",
        "route": "daily-region-data",
        "ba": ba,
        "year": year,
        "tz": "Eastern",
    }

    def fetch() -> Any:
        query: list[tuple[str, str | int | float | bool | None]] = [
            ("frequency", "daily"),
            ("data[0]", "value"),
            ("facets[respondent][]", ba),
            ("facets[type][]", "D"),
            ("facets[timezone][]", "Eastern"),
            ("start", f"{year}-01-01"),
            ("end", f"{year}-12-31"),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("length", "5000"),
        ]
        if settings.eia_api_key:
            query.append(("api_key", settings.eia_api_key))
        resp = httpx.get(
            f"{settings.eia_base_url}/electricity/rto/daily-region-data/data",
            params=query,
            timeout=settings.econ_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            hint = "invalid WATERMARK_EIA_API_KEY" if settings.eia_api_key else "no key set"
            raise Eia930Error(
                f"EIA-930 daily returned non-JSON ({hint}): {resp.text[:60]!r}"
            ) from exc
        rows = (((body or {}).get("response") or {}).get("data")) or []
        vals = [float(r["value"]) for r in rows if r.get("value") is not None]
        if not vals:
            # An empty annual-load response must not become a 0 GWh/yr denominator (A2/#1638):
            # a wrong BA code or a silent hiccup would otherwise be committed as zero.
            raise Eia930Error(
                f"EIA-930 daily demand for {ba} {year} returned no daily values — refusing to "
                "report a zero annual load (wrong BA code or empty response)"
            )
        return {"ba": ba, "year": year, "days": len(vals), "annual_demand_mwh": sum(vals)}

    payload = cast(
        "dict[str, Any]",
        cached_get(
            "eia930",
            params,
            fetch,
            cache_dir=settings.econ_cache_dir,
            offline=settings.econ_offline,
            fixtures_dir=settings.econ_fixtures_dir,
        ),
    )
    if int(payload["days"]) <= 0 or not payload["annual_demand_mwh"]:
        # Defends the offline path: a committed fixture that reduced to zero days/demand must
        # raise on read, not become a 0 GWh/yr denominator (A2/#1638).
        raise Eia930Error(
            f"EIA-930 daily-demand payload for {payload['ba']} {payload['year']} is empty/zero — "
            "refusing to report a zero annual load"
        )
    return ProvenancedValue.from_connector(
        round(payload["annual_demand_mwh"] / 1000.0, 1),
        "GWh/yr",
        citation=f"EIA-930 daily demand sum, {payload['ba']} {payload['year']} "
        f"({payload['days']} days, Eastern tz)",
        # The data year is the vintage (G1/#1644) — and the one the load-share drift guard
        # reads back off this value, so it must be the payload's year, not the request's.
        asof=str(payload["year"]),
    )


def derive_interchange_comparison(
    *,
    interchange: BAInterchange | None = None,
    settings: Settings | None = None,
) -> CampusInterchangeComparison:
    """Situate the campus load against the BA's interchange & coincident-peak adequacy.

    C1/C2/#1638: the headline is no longer an "in-BA generation headroom" (mean net
    generation - mean demand), which by the EIA-930 identity D = NG - TI is algebraically
    net interchange and made the "no imports needed" conclusion circular. Adequacy is judged
    at the **coincident peak** (the binding case for a flat 24x7 load), using the window peak
    demand that was previously collected and discarded.
    """
    settings = settings or get_settings()
    if interchange is None:
        # Per-site BA (B2/#1639): a pinned MISO/SPP site pulls its own EIA-930 respondent; PJM
        # is the default for the (all-PJM) network today, not an assumption baked into the pull.
        ba_code = active_profile(settings).ba_code or "PJM"
        bai = fetch_ba_interchange(ba=ba_code, settings=settings)
    else:
        bai = interchange
    power = derive_power_basis(settings=settings)
    if power is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility (SiteProfile.facility is None) — "
            "the campus interchange comparison needs a facility load"
        )

    draw = power.facility_draw.value
    demand = bai.demand_mean_mw.value
    demand_peak = bai.demand_peak_mw.value
    netgen = bai.net_generation_mean_mw.value
    ti = bai.total_interchange_mean_mw.value
    # A3/#1638: a zero/absent BA denominator means a broken upstream (empty connector, fixture
    # drift), not a negligible campus share — refuse to synthesize a 0% share (cf. #1103). After
    # A2 a non-empty window guarantees these, but guard explicitly at the share math too.
    if not demand or not demand_peak:
        raise ValueError(
            f"{bai.ba} mean/peak demand is zero/absent ({demand!r}/{demand_peak!r}) — cannot "
            "size the campus against a broken demand denominator"
        )
    if not ti:
        raise ValueError(
            f"{bai.ba} mean net interchange is zero/absent — cannot size the campus against a "
            "broken interchange denominator"
        )
    share_demand = draw / demand * 100.0
    share_peak = draw / demand_peak * 100.0
    vs_interchange = draw / abs(ti) * 100.0
    # Coincident-peak adequacy (C2): how far the window peak demand exceeds the mean in-BA net
    # generation. Not the balance identity (peak demand and mean net-gen are independent
    # quantities), so — unlike the dropped "headroom" — it is a genuine second signal. A
    # screening upper bound: generation also ramps at peak, which the reduced payload discards.
    peak_import_need = demand_peak - netgen
    import_dependent_at_peak = demand_peak > netgen

    flow = "a net exporter" if ti > 0 else "a net importer"
    interp = (
        f"Over this window {bai.ba} is {flow} on average (mean net interchange "
        f"{ti:,.0f} MW; the campus is ~{vs_interchange:.0f}% of that swing). But at the "
        f"window coincident peak, demand ({demand_peak:,.0f} MW) "
        f"{'exceeds' if import_dependent_at_peak else 'stays within'} the mean in-BA net "
        f"generation ({netgen:,.0f} MW) by {peak_import_need:,.0f} MW — so the BA "
        f"{'already leans on imports / peaking capacity at peak, and the campus ' + f'({draw:g} MW) adds on top of that' if import_dependent_at_peak else f'covers its own peak on average, with the campus ({draw:g} MW) a small addition'}. "
        f"The campus is ~{share_demand:.2f}% of mean demand and ~{share_peak:.2f}% of the peak."
    )

    log.info(
        "grid.interchange",
        ba=bai.ba,
        peak_import_need_mw=round(peak_import_need),
        import_dependent_at_peak=import_dependent_at_peak,
        campus_vs_interchange_pct=round(vs_interchange, 1),
    )
    return CampusInterchangeComparison(
        ba=bai.ba,
        campus_load_mw=ProvenancedValue.derived(
            round(draw, 1),
            "MW",
            citation=f"PowerBasis.facility_draw central (#87): {power.facility_draw.citation or ''}",
        ),
        ba_demand_mean_mw=bai.demand_mean_mw,
        ba_demand_peak_mw=bai.demand_peak_mw,
        ba_net_generation_mean_mw=bai.net_generation_mean_mw,
        ba_interchange_mean_mw=bai.total_interchange_mean_mw,
        campus_share_of_demand_pct=ProvenancedValue.derived(
            round(share_demand, 3),
            "percent",
            citation=f"campus {draw:g} MW / {bai.ba} mean demand {demand:,.0f} MW",
        ),
        campus_share_of_peak_demand_pct=ProvenancedValue.derived(
            round(share_peak, 3),
            "percent",
            citation=f"campus {draw:g} MW / {bai.ba} peak demand {demand_peak:,.0f} MW",
        ),
        campus_vs_interchange_pct=ProvenancedValue.derived(
            round(vs_interchange, 1),
            "percent",
            citation=f"campus {draw:g} MW / |mean net interchange| {abs(ti):,.0f} MW",
        ),
        peak_import_need_mw=ProvenancedValue.derived(
            round(peak_import_need),
            "MW",
            citation=f"{bai.ba} peak demand {demand_peak:,.0f} - mean net generation {netgen:,.0f} MW "
            "(coincident-peak gap vs mean in-BA generation; screening upper bound)",
        ),
        import_dependent_at_peak=import_dependent_at_peak,
        interpretation=interp,
        caveats=[
            "A screening comparison over WINDOW aggregates, not an hourly dispatch or "
            "locational (LMP/congestion) model — the marginal unit varies hour to hour.",
            "The coincident-peak gap compares the window PEAK demand against the window MEAN "
            "net generation (the reduced payload discards hourly net-gen), so it is a "
            "screening upper bound on the peak deficit, not a reserve-margin calculation "
            "(installed capacity is not in the EIA-930 region-data feed).",
            "Net interchange is a BA-wide balance; it says nothing about transmission "
            "deliverability to the campus's specific bus (that is the #96 PJM-queue layer).",
            "The window is representative, not the full year; EIA-930 figures are "
            "connector-sourced and regenerable with a key.",
        ],
    )


def _reference_path(reference_dir: Path) -> Path:
    return reference_dir / "eia" / "ba-interchange.yaml"


def write_ba_interchange(interchange: BAInterchange, *, settings: Settings | None = None) -> str:
    """Persist the BA interchange slice as committed reference YAML; return the path.

    The output collection dir is derived from the catalog (``output_dir_for_command``, #630/#658) —
    ``interchange`` is a basin-shared, single-collection command, so its dir resolves cleanly —
    falling back to the historical ``reference/eia`` literal. (The per-site ``eia``/``grid``
    commands are *not* wired this way: they write via the ``SiteProfile`` relpath, which carries
    the ``{site}`` segment a single collection dir can't — see ``output_dir_for_command``.)
    """
    from watermark.catalog import output_dir_for_command

    settings = settings or get_settings()
    base = (
        output_dir_for_command("interchange", settings=settings) or settings.reference_dir / "eia"
    )
    path = base / "ba-interchange.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(interchange.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("grid.interchange.wrote", path=str(path))
    return str(path)


def load_ba_interchange(reference_dir: Path) -> BAInterchange | None:
    """Read the committed BA-interchange YAML, or ``None`` if absent."""
    path = _reference_path(reference_dir)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return BAInterchange.model_validate(data)
