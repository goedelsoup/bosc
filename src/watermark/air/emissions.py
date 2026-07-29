"""Genset emission-factor loaders + AP-42/permit reconciliation (Tier-0, #1175).

Two grounded sources feed the emissions inventory, each returning a
:class:`~watermark.air.model.GensetEmissionFactors`:

- :func:`ap42_factors` — the generic EPA **AP-42 §3.4** prior, read from the committed
  reference dataset (``data/reference/air/emission-factors/ap42-3.4.yaml``). The full
  criteria-pollutant set, on a per-MWh and per-engine-hour basis.
- :func:`permit_factors` — the site air permit's **certified** per-engine rates and
  Tier-2 standards, read from the committed permit extraction. Partial (the pollutants
  the permit isolates) but higher confidence.

:func:`reconcile` puts them side by side per pollutant. AP-42 is the modeling default;
the permit is the cross-check (and it typically comes in *lower* — a modern Tier-2 engine
beats AP-42 "uncontrolled"). :func:`load_emission_factors` is the profile-driven entry
point: it resolves the engine rating and permit path from the active site, never a
hardcoded Lima/Bistrozzi value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from watermark.air.model import (
    CAPPED_POLLUTANTS,
    POLLUTANTS,
    EmissionFactor,
    FactorBasis,
    FactorReconciliation,
    GensetEmissionFactors,
    LoadRegime,
    Pollutant,
)
from watermark.config import Settings, get_settings
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# The committed AP-42 §3.4 reference dataset, relative to ``settings.reference_dir``.
_AP42_RELPATH = "air/emission-factors/ap42-3.4.yaml"

# Ultra-low-sulfur diesel cap (40 CFR 1090.305): 15 ppm S = 0.0015 wt-%. The AP-42 SOx
# factor scales with fuel sulfur; evaluated here at the permit fuel spec.
_ULSD_SULFUR_WT_PCT = 0.0015


def _load_ap42(settings: Settings) -> dict[str, Any]:
    path = settings.reference_dir / _AP42_RELPATH
    if not path.is_file():
        raise FileNotFoundError(f"AP-42 §3.4 reference dataset missing: {path}")
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _engine_mw_from_profile(settings: Settings) -> ProvenancedValue | None:
    """The site's per-engine rated output, from its disclosed facility (or ``None``)."""
    fac = active_profile(settings).campus
    if fac is None or fac.genset_mw is None or fac.air_permit_citation is None:
        # No facility, or a site-plan-grounded facility with no disclosed gensets / air permit —
        # no permit-grounded engine rating to base AP-42/permit factors on.
        return None
    return ProvenancedValue.from_document(
        fac.genset_mw, "MW", citation=fac.air_permit_citation, confidence="medium"
    )


def ap42_factors(
    engine_mw: ProvenancedValue,
    *,
    fuel: str = "diesel",
    fuel_sulfur_wt_pct: float = _ULSD_SULFUR_WT_PCT,
    settings: Settings | None = None,
) -> GensetEmissionFactors:
    """Build the generic AP-42 §3.4 factor set for one engine rating.

    Per-MWh factors are the AP-42 ``lb/hp-hr`` (power-output) values scaled to MWh; the
    per-engine-hour factors are those times ``engine_mw`` (rated-load output). PM is split
    into PM10/PM2.5 by the Table 3.4-2 size fractions; SO2 is evaluated at the fuel
    sulfur; VOC is the non-methane share of AP-42 TOC. Every factor is tagged
    ``reference`` (a published prior, not a fact about this facility).
    """
    settings = settings or get_settings()
    data = _load_ap42(settings)
    g = data["table_3_4_1_gaseous"]
    p = data["table_3_4_2_particulate"]
    conv = data["conversions"]
    cite = f"{data['source']['document']} ({data['source']['edition']})"

    # hp-hr per MWh: 1 MWh = 1000 kWh, 1 kWh = hp_per_kw hp-hr.
    hp_hr_per_mwh = float(conv["hp_per_kw"]) * 1000.0

    # PM size split from Table 3.4-2 (different vintage — used only as fractions, never added).
    total_pm = float(p["total_particulate_lb_per_mmbtu"])
    pm10_frac = float(p["total_pm10_lb_per_mmbtu"]) / total_pm
    pm25_frac = (
        float(p["filterable_lt_1um_lb_per_mmbtu"]) + float(p["condensable_lb_per_mmbtu"])
    ) / total_pm

    pm_out = float(g["pm"]["power_output_lb_per_hp_hr"])
    sox_out = float(g["sox"]["power_output_lb_per_hp_hr_per_pct_s"]) * fuel_sulfur_wt_pct
    voc_out = float(g["toc_as_ch4"]["power_output_lb_per_hp_hr"]) * float(
        g["toc_nonmethane_weight_fraction"]
    )

    # (pollutant -> lb/hp-hr output factor, provenance note)
    out_factors: dict[Pollutant, tuple[float, str]] = {
        "NOx": (
            float(g["nox_uncontrolled"]["power_output_lb_per_hp_hr"]),
            "Table 3.4-1 NOx uncontrolled",
        ),
        "CO": (float(g["co"]["power_output_lb_per_hp_hr"]), "Table 3.4-1 CO"),
        "PM10": (pm_out * pm10_frac, "Table 3.4-1 PM x Table 3.4-2 PM10 fraction"),
        "PM2.5": (
            pm_out * pm25_frac,
            "Table 3.4-1 PM x Table 3.4-2 (filterable <1µm + condensable) fraction",
        ),
        "SO2": (sox_out, f"Table 3.4-1 SOx at {fuel_sulfur_wt_pct:g} wt-% fuel S (ULSD)"),
        "VOC": (voc_out, "Table 3.4-1 TOC x 0.91 non-methane fraction"),
    }

    factors: dict[Pollutant, EmissionFactor] = {}
    for pol in POLLUTANTS:
        lb_per_hp_hr, why = out_factors[pol]
        per_mwh = lb_per_hp_hr * hp_hr_per_mwh
        per_hr = per_mwh * engine_mw.value
        factors[pol] = EmissionFactor(
            pollutant=pol,
            per_mwh=ProvenancedValue.from_reference(
                round(per_mwh, 5), "lb/MWh", citation=f"{cite}: {why}"
            ),
            per_engine_hour=ProvenancedValue.derived(
                round(per_hr, 4),
                "lb/hr",
                citation=f"{round(per_mwh, 5):g} lb/MWh x {engine_mw.value:g} MW rated",
            ),
        )

    return GensetEmissionFactors(
        basis="ap42",
        load_regime="load",  # AP-42 §3.4 gives a single rated/full-load factor set
        engine_mw=engine_mw,
        fuel=fuel,
        factors=factors,
        citation=f"{cite}, data/reference/{_AP42_RELPATH}",
        note=(
            "Generic AP-42 §3.4 uncontrolled prior (ratings B-E) for a large stationary "
            "diesel engine at rated load — a modeling default, not the site's certified "
            "rates. Expected to run high vs a Tier-2 engine; reconcile against the permit. "
            "AP-42 §3.4 does not resolve a low/idle-load point (use the permit basis for "
            "readiness-testing scenarios)."
        ),
    )


def permit_factors(
    engine_mw: ProvenancedValue,
    *,
    permit_path: Path,
    load_regime: LoadRegime = "load",
) -> GensetEmissionFactors:
    """Build the certified factor set from a site air-permit extraction.

    Reads the per-engine ``lb/hr`` rates the permit isolates (the capped NOx/CO) at the
    requested load point — ``"load"`` uses the ``>25% load`` rates (a reliability dispatch
    carrying real load, the worst case the synthetic-minor demonstration turns on),
    ``"idle"`` uses the ``≤25% load`` rates (readiness/maintenance testing) — plus the
    Tier-2 PM standard. Partial by construction: a permit does not isolate every pollutant,
    so only the grounded ones are populated. Rates are ``document`` provenance.
    """
    data = cast("dict[str, Any]", yaml.safe_load(permit_path.read_text(encoding="utf-8")))
    air = data["action"]  # the air-permit structured fields hang off the recorded action
    caps = air["facility_wide_limits"]
    rates = caps["per_engine_rates_lb_per_hr"]
    std = air["engine_emission_standards"]
    fuel_spec = air.get("fuel_spec", {})
    fuel = str(fuel_spec.get("fuels", "diesel"))
    rel = permit_path.name
    load_label = ">25% load" if load_regime == "load" else "≤25% load"
    cite = f"OEPA Air PTI (data/extracted/permits/{rel})"

    # Data-hall gensets (P001-P114). The load point selects the certified per-hour rate.
    hall = rates["P001-P114"]
    nox_key = "nox_gt_25pct_load" if load_regime == "load" else "nox_le_25pct_load"
    co_key = "co_gt_25pct_load" if load_regime == "load" else "co_le_25pct_load"
    nox_hr = float(hall[nox_key])
    co_hr = float(hall[co_key])

    # Tier-2 PM standard (g/kWh -> lb/MWh): diesel PM is predominantly fine, so PM10≈PM2.5.
    pm_g_per_kwh = float(std["pm_g_per_kwh"])
    pm_lb_per_mwh = pm_g_per_kwh * 1000.0 / 453.592  # g/kWh * 1000 kWh/MWh / g-per-lb

    def _factor(pol: Pollutant, per_hr: float, per_mwh: float, why: str) -> EmissionFactor:
        return EmissionFactor(
            pollutant=pol,
            per_mwh=ProvenancedValue.from_document(
                round(per_mwh, 5), "lb/MWh", citation=f"{cite}: {why}"
            ),
            per_engine_hour=ProvenancedValue.from_document(
                round(per_hr, 4), "lb/hr", citation=f"{cite}: {why}"
            ),
        )

    factors: dict[Pollutant, EmissionFactor] = {
        "NOx": _factor(
            "NOx", nox_hr, nox_hr / engine_mw.value, f"per-engine NOx at {load_label} (B.4.b)"
        ),
        "CO": _factor(
            "CO", co_hr, co_hr / engine_mw.value, f"per-engine CO at {load_label} (B.4.b)"
        ),
        "PM10": _factor(
            "PM10",
            pm_lb_per_mwh * engine_mw.value,
            pm_lb_per_mwh,
            f"Tier-2 PM standard {pm_g_per_kwh:g} g/kWh (40 CFR 60 IIII)",
        ),
        "PM2.5": _factor(
            "PM2.5",
            pm_lb_per_mwh * engine_mw.value,
            pm_lb_per_mwh,
            f"Tier-2 PM standard {pm_g_per_kwh:g} g/kWh (diesel PM ~ all PM2.5)",
        ),
    }

    return GensetEmissionFactors(
        basis="permit",
        load_regime=load_regime,
        engine_mw=engine_mw,
        fuel=fuel,
        factors=factors,
        citation=cite,
        note=(
            f"Site permit certified rates: per-engine NOx/CO at the {load_label} point "
            "+ the Tier-2 PM standard. SO2/VOC are sub-1-tpy facility-wide and not "
            "isolated per engine. The PM standard is load-independent (g/kWh certification)."
        ),
    )


def reconcile(
    ap42: GensetEmissionFactors, permit: GensetEmissionFactors
) -> list[FactorReconciliation]:
    """Put AP-42 and permit factors side by side per pollutant (the #1175 reconciliation).

    For each pollutant present in either source, report the per-engine-hour rates and the
    AP-42/permit ratio. Where only one source grounds a pollutant, the ratio is ``None``.
    """
    out: list[FactorReconciliation] = []
    for pol in POLLUTANTS:
        a = ap42.factor(pol)
        p = permit.factor(pol)
        a_hr = a.per_engine_hour.value if a is not None else None
        p_hr = p.per_engine_hour.value if p is not None else None
        if a_hr is None and p_hr is None:
            continue
        # Explicit None checks — a valid 0.0 rate is "present", not absent, so it must not
        # be misread as ungrounded. Division still guards against a zero denominator.
        if a_hr is None or p_hr is None:
            ratio = None
            note = (
                "only AP-42 grounds this pollutant"
                if p_hr is None
                else "only the permit grounds this"
            )
        elif p_hr == 0:
            ratio = None
            note = "permit rate is zero — ratio undefined"
        else:
            ratio = round(a_hr / p_hr, 3)
            if pol in CAPPED_POLLUTANTS:
                hot = "over" if ratio >= 1 else "under"
                note = f"AP-42 uncontrolled {hot}-predicts the certified Tier-2 rate by {abs(ratio - 1) * 100:.0f}%"
            else:
                note = "AP-42 generic vs permit Tier-2 standard"
        out.append(
            FactorReconciliation(
                pollutant=pol,
                ap42_per_engine_hour_lb=a_hr,
                permit_per_engine_hour_lb=p_hr,
                ratio_ap42_over_permit=ratio,
                note=note,
            )
        )
    return out


def _permit_path(settings: Settings) -> Path:
    """The active site's air-permit extraction path from its profile (#1180).

    Resolved from ``SiteFacility.air_permit_relpath`` — per-site, never a hardcoded Lima
    default. ``settings.extracted_dir`` is a *shared* tree, so a facility-bearing site that
    hasn't wired its own permit (``air_permit_relpath is None``) must refuse rather than
    silently resolve another site's relpath: it raises ``NotImplementedError`` (a caller with
    an out-of-band permit can still pass an explicit ``permit_path`` to ``permit_factors``).
    """
    fac = active_profile(settings).campus
    relpath = fac.air_permit_relpath if fac is not None else None
    if relpath is None:
        raise NotImplementedError(
            f"site {settings.site!r} has no wired air-permit path — set "
            "SiteFacility.air_permit_relpath in its profile (#1180) to ground permit-based "
            "factors + NSR caps, or pass an explicit permit_path to permit_factors()."
        )
    return settings.extracted_dir / relpath


def nsr_caps(permit_path: Path) -> dict[str, ProvenancedValue]:
    """The synthetic-minor NSR facility-wide caps (tpy) from a permit extraction.

    The federally-enforceable annual limits the permit was engineered to stay under —
    for Lima's P0138965, NOx 235.62 / CO 96.06 tpy (rolling 12-month, P001-P115 combined).
    ``document`` provenance (read from the issued permit).
    """
    data = cast("dict[str, Any]", yaml.safe_load(permit_path.read_text(encoding="utf-8")))
    caps = data["action"]["facility_wide_limits"]
    rel = permit_path.name
    cite = f"OEPA Air PTI facility-wide synthetic-minor cap (data/extracted/permits/{rel})"
    out: dict[str, ProvenancedValue] = {}
    for pol, key in (("NOx", "nox_tpy"), ("CO", "co_tpy")):
        if key in caps:
            out[pol] = ProvenancedValue.from_document(
                float(caps[key]), "tpy", citation=f"{cite}: {caps.get('basis', '')}".rstrip(": ")
            )
    return out


def load_nsr_caps(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Profile-driven NSR caps for the active site.

    Empty when the site has no disclosed facility, or no wired air permit yet
    (``SiteFacility.air_permit_relpath is None``): honestly "no caps known" rather than
    silently inheriting another site's caps. An AP-42 tonnage run on such a site simply
    skips the cap check; a permit-basis run raises via :func:`_permit_path`.
    """
    settings = settings or get_settings()
    fac = active_profile(settings).campus
    if fac is None or fac.air_permit_relpath is None:
        return {}
    return nsr_caps(_permit_path(settings))


def load_emission_factors(
    *,
    basis: FactorBasis = "ap42",
    load_regime: LoadRegime = "load",
    settings: Settings | None = None,
) -> GensetEmissionFactors | None:
    """Profile-driven factor set for the active site, or ``None`` if it has no campus.

    Resolves the per-engine rating from the site's data-center ``SiteFacility``; a site with no
    disclosed campus (``SiteProfile.campus is None`` — no facility at all, or a
    ``federal_installation``, which has no genset fleet by construction, #1664) returns ``None``
    (grid-backdrop only, per the readiness layer). AP-42 has no idle-load point — request
    ``load_regime="idle"`` only on the permit basis.
    """
    settings = settings or get_settings()
    engine_mw = _engine_mw_from_profile(settings)
    if engine_mw is None:
        log.info("air.factors.no_facility", site=settings.site)
        return None
    if basis == "permit":
        return permit_factors(
            engine_mw, permit_path=_permit_path(settings), load_regime=load_regime
        )
    if load_regime == "idle":
        raise ValueError(
            "AP-42 §3.4 has no idle/low-load factor — use basis='permit' for a "
            "readiness-testing (idle) scenario, or load_regime='load' for AP-42."
        )
    return ap42_factors(engine_mw, settings=settings)
