"""Event-anchored dispatch calibration: dimension the trigger by a captured real event.

The #1176 dispatch trigger (:mod:`watermark.air.dispatch`) maps BA-wide EIA-930 signals to
a runtime band through an *escalation fraction* that is honestly `[inference]` — ungrounded
until a real reliability-triggered dispatch is captured. Issue #1174 captured one: the PJM
hot-weather **FPA §202(c) emergency** (DOE Order 202-26-33), whose signed order *authorizes*
data-center backup generation over a **verified, bounded window**. This module reads that
committed event record (``data/extracted/grid/*.event.yaml``) and anchors the trigger to it.

The calibration is the honest half of #1182 that Tier-0 can carry without AERMOD: it replaces
the abstract BA-wide fraction with the event's own dimensions.

- The **authorized window** (e.g. Order 202-26-33's 72 h effective→expiry) is `[verified]` /
  `[derived]` — read straight from the captured order. It is the defensible **ceiling** on
  authorized backup-gen dispatch for one such event.
- Whether *this* facility actually ran, and for how long inside that window, stays `[open]`
  (``facility_dispatch_confirmed=False``) — the order is RTO-wide and names no facility, and
  the corridor facility (P0138965) was pre-operational. So the per-event **duty fraction**
  and the **events-per-year** recurrence remain labeled `[inference]`.

Net: ``runtime = authorized_window_hours x duty_fraction x events_per_year`` per engine, with
the window verified and only the intra-window duty / recurrence assumed — a materially firmer
anchor than the pure escalation fraction, and one that "demonstrates how the trigger behaves
now" against a real event. Feeds the existing :func:`watermark.air.scenario.evaluate` cap check.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.air.scenario import AirScenario, reliability_dispatch_scenario
from watermark.config import Settings, get_settings
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

# The corridor's captured event. Basin/RTO-shared (PJM spans the whole region, not one site),
# so this is not a per-site knob — a second corridor event would be captured as its own file
# and passed via ``event_relpath``. Relative to ``settings.extracted_dir``.
_DEFAULT_EVENT_RELPATH = "grid/pjm-202c-emergency-2026.event.yaml"


class EventAnchoredAssumptions(BaseModel):
    """The remaining `[inference]` after the event grounds the window: duty + recurrence.

    ``duty_fraction_*`` is the share of the authorized window the fleet is assumed to actually
    run (unobserved — the order authorizes availability, not a logged runtime). ``high`` = 1.0
    is the full authorized window, the verified ceiling. ``events_per_year`` is how many such
    authorized events recur annually (the captured one is a single 2026 summer §202(c) order;
    DOE issued several 202(c) orders that season, so >1 is plausible but uncounted here).
    """

    model_config = ConfigDict(extra="forbid")

    duty_fraction_low: float = 0.05
    duty_fraction_central: float = 0.25
    duty_fraction_high: float = 1.0
    events_per_year: float = 1.0
    rationale: str = (
        "duty_fraction = share of the authorized window the fleet actually runs (unobserved — "
        "the order authorizes availability, not a logged runtime); events_per_year = annual "
        "recurrence of such authorized events. Both [inference], overridable; the window itself "
        "is [verified] from the captured order."
    )


class CapturedDispatchEvent(BaseModel):
    """A captured, real reliability event that dimensions the dispatch model (#1174).

    ``authorized_window_hours`` is the backup-generation authorization window read from the
    captured order (verified). ``backup_generation_authorized`` records that the order
    authorized data-center backup-gen dispatch; ``facility_dispatch_confirmed`` stays ``False``
    until a facility-level runtime record lands — the event does **not** establish that any
    specific facility ran (omission over invention).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    order_id: str | None
    window_start: str
    window_end: str
    authorized_window_hours: ProvenancedValue
    backup_generation_authorized: bool
    facility_dispatch_confirmed: bool
    source_relpath: str
    citations: list[str] = []
    caveats: list[str] = []


class EventAnchoredRuntime(BaseModel):
    """A backup fleet's forced runtime band anchored to a captured event (the #1182 calibration).

    ``runtime_hours_*`` are per-engine hours per year. ``runtime_hours_high`` is the verified
    ceiling (full authorized window x recurrence); the lower band points scale it by the
    `[inference]` duty fraction. Unlike the pure escalation-fraction band, the magnitude is
    now dimensioned by a real order's window.
    """

    model_config = ConfigDict(extra="forbid")

    event: CapturedDispatchEvent
    events_per_year: ProvenancedValue
    runtime_hours_low: ProvenancedValue
    runtime_hours_central: ProvenancedValue
    runtime_hours_high: ProvenancedValue
    assumptions: EventAnchoredAssumptions
    caveats: list[str] = []


def _parse_dt(value: str) -> datetime | None:
    """Parse an event timestamp, tolerating a trailing tz label (e.g. ``'2026-06-30T23:59 ET'``)."""
    token = value.strip().split(" ")[0]
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def _authorized_window(doc: dict[str, Any]) -> tuple[str | None, float, str, bool]:
    """Return (order_id, hours, citation, verified) for the backup-gen authorization window.

    Prefers the order carrying both ``effective`` and ``expires`` timestamps (the bounded
    backup-generation authorization). Falls back to the statutory-emergency window dates when
    no order isolates an explicit window.
    """
    orders = doc.get("orders") or []
    for order in orders:
        eff, exp = order.get("effective"), order.get("expires")
        if not (eff and exp):
            continue
        start, end = _parse_dt(str(eff)), _parse_dt(str(exp))
        if start is None or end is None:
            continue
        hours = round((end - start).total_seconds() / 3600.0, 1)
        if hours <= 0:
            continue
        oid = order.get("id")
        return (str(oid) if oid is not None else None, hours, f"DOE Order {oid} {eff}..{exp}", True)

    # Fallback: the statutory emergency window (dates only) — a looser bound.
    win = (doc.get("event") or {}).get("statutory_emergency_window") or {}
    start, end = _parse_dt(str(win.get("start", ""))), _parse_dt(str(win.get("end", "")))
    if start is not None and end is not None:
        hours = round((end - start).total_seconds() / 3600.0, 1)
        if hours > 0:
            return (
                None,
                hours,
                f"statutory emergency window {win.get('start')}..{win.get('end')}",
                True,
            )
    return (None, 0.0, "no bounded window in the captured event", False)


def _linkage_tag(doc: dict[str, Any], *needles: str) -> str | None:
    """The provenance tag of the first ``corridor_linkage`` entry whose key matches a needle."""
    linkage = doc.get("corridor_linkage") or {}
    for key, body in linkage.items():
        if any(n in key for n in needles) and isinstance(body, dict):
            return cast("str | None", body.get("tag"))
    return None


def load_captured_event(
    *,
    event_relpath: str = _DEFAULT_EVENT_RELPATH,
    settings: Settings | None = None,
) -> CapturedDispatchEvent | None:
    """Read a committed grid-reliability event record into a :class:`CapturedDispatchEvent`.

    Returns ``None`` when the record is absent, so a site/checkout without the captured event
    degrades to the pure #1176 band rather than breaking.
    """
    settings = settings or get_settings()
    path = settings.extracted_dir / event_relpath
    if not path.is_file():
        log.info("air.calibration.no_event", path=str(path))
        return None
    doc = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))

    event = doc.get("event") or {}
    win = event.get("statutory_emergency_window") or {}
    order_id, hours, cite, verified = _authorized_window(doc)

    backup_authorized = (
        _linkage_tag(doc, "backup_dispatch_authorized", "dispatch_authorized") == "[verified]"
    )
    facility_confirmed = _linkage_tag(doc, "facility", "genset") == "[verified]"

    window_pv = (
        ProvenancedValue.from_document(hours, "hr", citation=cite, confidence="high")
        if verified
        else ProvenancedValue.assume(0.0, "hr", why=cite)
    )

    caveats = [
        "The authorized window is [verified] from the captured order; whether this facility "
        "ran, and for how long inside the window, is [open] — the order is RTO-wide and names "
        "no facility. facility_dispatch_confirmed stays False until a facility runtime record lands.",
    ]
    if not backup_authorized:
        caveats.append(
            "Backup-generation dispatch authorization not asserted [verified] in this record."
        )

    captured = CapturedDispatchEvent(
        name=str(event.get("name") or doc.get("meta", {}).get("subject") or path.stem),
        order_id=order_id,
        window_start=str(win.get("start", "")),
        window_end=str(win.get("end", "")),
        authorized_window_hours=window_pv,
        backup_generation_authorized=backup_authorized,
        facility_dispatch_confirmed=facility_confirmed,
        source_relpath=event_relpath,
        citations=[cite],
        caveats=caveats,
    )
    log.info(
        "air.calibration.loaded_event",
        name=captured.name,
        order_id=order_id,
        window_hours=hours,
        facility_confirmed=facility_confirmed,
    )
    return captured


def event_anchored_runtime(
    event: CapturedDispatchEvent,
    *,
    assumptions: EventAnchoredAssumptions | None = None,
) -> EventAnchoredRuntime:
    """Anchor the forced-runtime band to a captured event's window (the #1182 calibration).

    ``runtime = authorized_window_hours x duty_fraction x events_per_year`` per engine. The
    ``high`` point (full duty) is `[derived]` from the verified window x recurrence — the
    defensible ceiling; ``low``/``central`` scale it by the unobserved intra-window duty and
    are `[inference]`.
    """
    assumptions = assumptions or EventAnchoredAssumptions()
    window = event.authorized_window_hours.value
    epy = assumptions.events_per_year

    events_pv = ProvenancedValue.assume(
        epy,
        "events/yr",
        why="assumed annual recurrence of such authorized reliability events — [inference]; "
        "the captured event is a single 2026 summer §202(c) authorization",
    )

    def _runtime(frac: float, label: str, *, derived: bool) -> ProvenancedValue:
        hours = round(window * frac * epy, 2)
        cite = (
            f"{window:g} hr authorized window x {frac:g} {label} duty x {epy:g} events/yr "
            f"(anchored to {event.name}"
            + (f", Order {event.order_id}" if event.order_id else "")
            + ")"
        )
        if derived:
            return ProvenancedValue.derived(hours, "hr/yr", citation=cite, confidence="medium")
        return ProvenancedValue.assume(
            hours, "hr/yr", why=cite + " — [inference], intra-window duty unobserved"
        )

    caveats = [
        *event.caveats,
        "Reliability / compliance stress-test only — economic peak-shaving and demand-response "
        "are out of scope for this epic.",
        "runtime_hours_high is the verified authorized-window ceiling (full duty); the lower band "
        "points apply an [inference] intra-window duty fraction.",
    ]
    est = EventAnchoredRuntime(
        event=event,
        events_per_year=events_pv,
        runtime_hours_low=_runtime(assumptions.duty_fraction_low, "low", derived=False),
        runtime_hours_central=_runtime(assumptions.duty_fraction_central, "central", derived=False),
        runtime_hours_high=_runtime(assumptions.duty_fraction_high, "high", derived=True),
        assumptions=assumptions,
        caveats=caveats,
    )
    log.info(
        "air.calibration.runtime",
        window_hours=window,
        central_hr=est.runtime_hours_central.value,
        high_hr=est.runtime_hours_high.value,
    )
    return est


def calibrate_dispatch(
    *,
    event_relpath: str = _DEFAULT_EVENT_RELPATH,
    assumptions: EventAnchoredAssumptions | None = None,
    settings: Settings | None = None,
) -> EventAnchoredRuntime | None:
    """Load the captured event and anchor the runtime band to it (``None`` if no event)."""
    settings = settings or get_settings()
    event = load_captured_event(event_relpath=event_relpath, settings=settings)
    if event is None:
        return None
    return event_anchored_runtime(event, assumptions=assumptions)


def event_anchored_scenario(
    runtime: EventAnchoredRuntime,
    *,
    band: str = "high",
    factors_basis: str = "permit",
) -> AirScenario:
    """Build an emissions scenario from an event-anchored runtime band point.

    Names the scenario ``reliability_dispatch_event_<band>`` (distinct from the pure #1176
    band) and cites the captured event, so the committed artifact self-documents its anchor.
    Feed to :func:`watermark.air.scenario.evaluate` for the NSR cap check.
    """
    point = {
        "low": runtime.runtime_hours_low,
        "central": runtime.runtime_hours_central,
        "high": runtime.runtime_hours_high,
    }[band]
    ev = runtime.event
    citation = (
        f"event-anchored dispatch ({band} band): {point.value:g} hr/yr per engine, "
        f"anchored to {ev.name}"
        + (f" (Order {ev.order_id})" if ev.order_id else "")
        + " — window [verified], duty/recurrence [inference]; facility dispatch [open]"
    )
    scenario = reliability_dispatch_scenario(
        point.value,
        band=f"event_{band}",
        citation=citation,
        factors_basis=cast("Any", factors_basis),
    )
    return scenario
