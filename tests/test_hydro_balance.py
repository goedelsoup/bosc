"""End-to-end water balance + low-flow assimilative screen, and the provenance invariant."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from watermark.config import Settings
from watermark.hydrology import balance as bal
from watermark.hydrology import lowflow
from watermark.hydrology.assimilative import (
    assimilative_findings,
    check_assimilative,
    dilution_flag,
)
from watermark.hydrology.balance import build_water_balance
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.model import Node, ProvenancedValue, WaterBalance, WaterBalanceNode
from watermark.pipeline.hydrology import run_baseline


def test_cited_low_flows_load(hydro_settings: Settings) -> None:
    flows = lowflow.load_low_flows(settings=hydro_settings)
    assert flows["dug run"].value == pytest.approx(0.78)
    assert flows["pike run"].value == pytest.approx(0.03)
    # Both are read straight from Ohio EPA fact sheets — document-sourced and cited.
    for pv in flows.values():
        assert pv.citation
        assert pv.source in {"document", "derived"}


def test_derived_low_flow_entries_disclose_their_weakness(hydro_settings: Settings) -> None:
    """The verified-negative exception must stay narrow and self-disclosing (#886).

    ``low-flow-7q10.yaml`` is the cited regulatory table, and it admits a ``source: derived``
    entry only where the fact sheet demonstrably states no design low flow at all. That
    exception is worth exactly as much as its disclosure, so an entry taking it must not be
    able to pass as a cited one: it carries ``confidence: low`` and says in its own citation
    that it is derived. Wilmington's Lytle Creek is the case; if a second reach ever takes the
    exception, this holds it to the same bar rather than letting the precedent widen quietly.
    """
    flows = lowflow.load_low_flows(settings=hydro_settings)
    derived = {name: pv for name, pv in flows.items() if pv.source != "document"}
    assert set(derived) == {"lytle creek"}, (
        "a new source: derived entry appeared in the CITED low-flow table — that is allowed "
        "only under the verified-negative exception documented in that file's header; add it "
        "here deliberately, never by widening this assertion to make a test pass"
    )
    for name, pv in derived.items():
        assert pv.confidence == "low", f"{name}: a derived design low flow is not high-confidence"
        assert pv.citation and "DERIVED" in pv.citation, (
            f"{name}: the citation must say it is derived, so it can never be quoted as cited"
        )

    # The acute peer reads the same entry's provenance rather than relabelling it `document`.
    acute = lowflow.load_acute_low_flows(settings=hydro_settings)
    assert acute["lytle creek"].source == "derived"
    assert acute["lytle creek"].confidence == "low"

    # The seasonal peer too. Lytle Creek carries no summer 30Q10 — only the ANNUAL 30Q10 was
    # derived — so the summer floor must be absent rather than silently filled from it.
    summer, one_q10 = lowflow.seasonal_low_flows("Lytle Creek", settings=hydro_settings)
    assert summer is None
    assert one_q10 is not None and one_q10.source == "derived"


def test_low_flow_lookup_normalizes_river_mile(hydro_settings: Settings) -> None:
    pv = lowflow.low_flow_for("Dug Run at River Mile 3.1", settings=hydro_settings)
    assert pv is not None and pv.value == pytest.approx(0.78)


def test_baseline_flags_tributary_violations(hydro_settings: Settings) -> None:
    balance, checks, findings = run_baseline(settings=hydro_settings, live=True)

    # Four WWTPs with document design flows: the three small county plants plus the
    # City of Lima WWTP (18.5 MGD, OEPA 2PE00000 / OH0026069 — the major municipal
    # receiving plant, counted since #1536); the abstraction reach is live.
    assert len(balance.by_role("wwtp")) == 4
    abstraction = balance.node("lima-wtp")
    assert abstraction is not None and abstraction.inflow is not None
    assert abstraction.inflow.source == "connector"  # grounded by the NWIS fixture
    # The fixture reading is NWIS provisional ("P"), so it enters low-confidence, not as
    # an authoritative approved value (#1602).
    assert abstraction.inflow.confidence == "low"

    # American II -> Dug Run is the binding, document-cited near-undiluted case.
    dug = next(c for c in checks if c.receiving_water == "Dug Run")
    assert dug.discharge.value == pytest.approx(1.857, abs=0.01)  # 1.2 MGD
    assert dug.dilution_ratio < 1.0 and dug.flag == "violation"

    # All three plants discharge more than their stream's entire 7Q10 (incl. the
    # Ottawa mainstem, whose 7Q10 is now cited from the Lima Refining fact sheet).
    violations = [f for f in findings if not f.ok]
    assert {f.subject.split(" -> ")[1] for f in violations} == {
        "Dug Run",
        "Pike Run",
        "Ottawa River",
    }


def test_wwtp_design_flow_sourced_from_structured_field_not_prose(hydro_settings: Settings) -> None:
    """WS-22 (issue 1622): the balance reads each WWTP's design flow from the structured
    routing.yaml ``design_flow_mgd`` (a document-cited field), not by first-match regex over the
    watch-items summary. Because Shawnee's post-expansion 3.0 MGD is now pinned structurally, the
    old 'summary states a flow expansion; used the first value' heuristic caveat no longer fires."""
    from watermark.hydrology.units import mgd_to_cfs

    balance = build_water_balance(settings=hydro_settings, live=False)
    flows = {n.node.id: n.return_flow for n in balance.nodes if n.return_flow is not None}
    # Structured design flows -> discharge (cfs), unchanged in value but no longer prose-derived.
    assert flows["watch-shawnee-ii-wwtp"].value == pytest.approx(mgd_to_cfs(3.0))
    assert flows["watch-american-ii-wwtp"].value == pytest.approx(mgd_to_cfs(1.2))
    assert flows["watch-lima-wwtp"].value == pytest.approx(mgd_to_cfs(18.5))
    # The campus FM-2 discharge is structured too.
    assert flows["bosc-campus"].value == pytest.approx(mgd_to_cfs(2.5))
    # The structured value's authoritative NPDES citation flows into the evidence record —
    # not a generic watch-item id (WS-22 provenance).
    assert "2PK00002" in (flows["watch-shawnee-ii-wwtp"].citation or "")
    assert "2PE00000" in (flows["watch-lima-wwtp"].citation or "")
    # No regex-fallback expansion caveat survives now that the value is structured.
    assert not any("flow expansion" in w for w in balance.warnings)
    assert not any("used the first value" in w for w in balance.warnings)


def test_design_mgd_prefers_structured_and_regex_is_a_fallback() -> None:
    """The resolver prefers the structured value; the prose regex is only a fallback that
    surfaces the multi-figure (expansion) heuristic, preserves the approximate ``~`` marker,
    and emits a structured log so a regex-sourced number is never silent."""
    import structlog

    # Structured wins outright — the prose isn't even consulted, so no expansion/approx flags.
    assert bal._design_mgd(3.0, "2.0 -> 3.0 MGD avg / 12.6 MGD peak", subject="x") == (
        3.0,
        False,
        False,
    )
    # No structured value -> first "N MGD" token; multiple figures raise the expansion flag.
    assert bal._design_mgd(None, "2.0 -> 3.0 MGD avg / 12.6 MGD peak", subject="x") == (
        3.0,
        True,
        False,
    )
    assert bal._design_mgd(None, "1.5 MGD design", subject="x") == (1.5, False, False)
    # An approximate transcription keeps its ``~`` provenance (returned as approximate=True).
    assert bal._design_mgd(None, "~2.5 MGD design", subject="x") == (2.5, False, True)
    # No figure at all -> no value, no expansion, not approximate.
    assert bal._design_mgd(None, "no flow stated here", subject="x") == (None, False, False)

    # The regex fallback emits `hydro.design_flow.regex_fallback` carrying subject, the selected
    # mgd, the count of matched figures, and the approximation flag (finding 4 / issue 1622).
    with structlog.testing.capture_logs() as logs:
        bal._design_mgd(None, "~2.5 MGD avg / 4.0 MGD peak", subject="Foo WWTP")
    events = [e for e in logs if e.get("event") == "hydro.design_flow.regex_fallback"]
    assert len(events) == 1
    ev = events[0]
    assert ev["subject"] == "Foo WWTP"
    assert ev["mgd"] == 2.5
    assert ev["matches"] == 2
    assert ev["approximate"] is True


def test_provenance_invariant(hydro_settings: Settings) -> None:
    """Every numeric input carries a source; document values carry a citation."""
    balance, _checks, _findings = run_baseline(settings=hydro_settings, live=True)
    values = balance.all_values()
    assert values  # not vacuous
    for pv in values:
        assert pv.source in ("document", "connector", "assumption", "derived")
        if pv.source == "document":
            assert pv.citation, f"document value without citation: {pv}"


def test_campus_consumptive_is_derived_not_placeholder(hydro_settings: Settings) -> None:
    # The campus cooling consumptive is the sourced power-based central (≈4.86 cfs from
    # the air permit x WUE), `derived` — not the old 0 cfs "unsourced placeholder".
    balance = build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is not None
    cu = campus.consumptive_use
    assert cu.source == "derived"
    assert cu.value == pytest.approx(4.86, abs=0.1)
    assert "cooling basis" in (cu.citation or "")
    # No stale "placeholder"/"unsourced"/"TBD" framing remains in the warnings.
    joined = " ".join(balance.warnings).lower()
    assert "placeholder" not in joined
    assert "unsourced" not in joined
    assert "tbd" not in joined


def test_fm2_grounds_both_the_return_flow_and_the_blowdown_bound(hydro_settings: Settings) -> None:
    """The FM-2 figure plays two roles from ONE document, so they are not independent (#1634).

    The campus ``return_flow`` (the routed discharge to Lima) and the cooling bracket's
    bottom-up upper bound (``SiteFacility.blowdown_mgd`` taken as tower blowdown) are the same
    ~2.5 MGD CMAR RFQ §A.6 discharge, held as two copies. Lock them to one figure: a silent
    divergence between the copies would otherwise read as two agreeing observations.
    """
    from watermark.hydrology.units import mgd_to_cfs
    from watermark.sites import active_profile

    facility = active_profile(hydro_settings).facility
    assert facility is not None and facility.blowdown_mgd is not None
    balance = build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.return_flow is not None
    assert campus.return_flow.value == pytest.approx(mgd_to_cfs(facility.blowdown_mgd), abs=0.01)
    # Both trace to the same FM-2 discharge — the shared provenance the coupling rests on.
    assert "fm2" in (campus.return_flow.citation or "").lower()
    assert "fm2" in (facility.blowdown_citation or "").lower()


def test_assimilative_matches_suffixed_receiving_water(hydro_settings: Settings) -> None:
    # A receiving water carrying a river-mile / place suffix ("Dug Run at River Mile 3.1")
    # must still resolve its cited 7Q10 ("dug run"): the lookup normalizes the same way
    # the cited table was keyed. Regression for the silent-skip bug where the suffixed
    # name missed the table and the discharge vanished from the screen.
    node = Node(
        id="x-wwtp", name="X WWTP", role="wwtp", receiving_water="Dug Run at River Mile 3.1"
    )
    wbn = WaterBalanceNode(
        node=node, return_flow=ProvenancedValue.from_document(2.0, "cfs", citation="test 2 cfs")
    )
    balance = WaterBalance(nodes=[wbn], warnings=[])
    checks = check_assimilative(balance, dict(lowflow.load_low_flows(settings=hydro_settings)))
    dug = next((c for c in checks if "Dug Run" in c.receiving_water), None)
    assert dug is not None, "suffixed receiving water must still resolve its cited 7Q10"
    assert dug.design_low_flow.value == pytest.approx(0.78)


def _wwtp(node_id: str, name: str, water: str, cfs: float) -> WaterBalanceNode:
    return WaterBalanceNode(
        node=Node(id=node_id, name=name, role="wwtp", receiving_water=water),
        return_flow=ProvenancedValue.from_document(cfs, "cfs", citation=f"{name} design"),
    )


def test_effluent_credited_denominator_credits_co_reach_permitted_effluent() -> None:
    """WS-15 (#1615): the dilution denominator can credit the permitted effluent already in the
    reach. A plant sharing its receiving water with other permitted dischargers gets a second,
    effluent-credited ratio; a plant alone on its stream stays at the conservative default."""
    low_flows = {
        "Ottawa River": ProvenancedValue.from_document(0.2, "cfs", citation="Ottawa 7Q10"),
        "Dug Run": ProvenancedValue.from_document(0.78, "cfs", citation="Dug Run 7Q10"),
    }
    balance = WaterBalance(
        nodes=[
            _wwtp("big", "Big WWTP", "Ottawa River", 28.0),
            _wwtp("small", "Small WWTP", "Ottawa River", 4.0),
            _wwtp("lone", "Lone WWTP", "Dug Run", 2.0),
        ],
        warnings=[],
    )
    checks = {c.discharger: c for c in check_assimilative(balance, low_flows)}

    # The conservative default (cited 7Q10 / discharge) is unchanged for every plant.
    small = checks["Small WWTP"]
    assert small.dilution_ratio == pytest.approx(0.2 / 4.0)
    assert small.flag == "violation"
    # Small WWTP shares the Ottawa with Big WWTP: its denominator credits Big's 28 cfs of effluent.
    assert small.upstream_returns is not None
    assert small.upstream_returns.source == "derived"
    assert small.upstream_returns.value == pytest.approx(28.0)
    assert "Big WWTP" in (small.upstream_returns.citation or "")
    assert small.effluent_credited_ratio == pytest.approx((0.2 + 28.0) / 4.0)
    assert small.effluent_credited_flag == dilution_flag(small.effluent_credited_ratio)
    # 7.05:1 — crediting the standing effluent flips it out of the violation band.
    assert small.effluent_credited_flag == "tight"

    # Big WWTP credits Small's 4 cfs, but its own 28 cfs still dwarfs it → stays a violation.
    big = checks["Big WWTP"]
    assert big.upstream_returns is not None and big.upstream_returns.value == pytest.approx(4.0)
    assert big.effluent_credited_ratio == pytest.approx((0.2 + 4.0) / 28.0)
    assert big.effluent_credited_flag == "violation"

    # Lone WWTP is the only permitted discharger on Dug Run → nothing to credit, stays default.
    lone = checks["Lone WWTP"]
    assert lone.upstream_returns is None
    assert lone.effluent_credited_ratio is None
    assert lone.effluent_credited_flag is None
    assert lone.dilution_ratio == pytest.approx(0.78 / 2.0) and lone.flag == "violation"


def test_acute_dilution_matches_the_1q10_design_flow() -> None:
    """WS-08 (#1608): the screen matches the design flow to the criterion type — chronic dilution
    at the 7Q10, acute at the sharper 1Q10. A cited 1Q10 = 0 cfs (a stream that stops at design
    low flow) yields a 0:1 acute ratio — no acute assimilative capacity — and a stream with no
    cited 1Q10 leaves the acute pair unset (omit, don't guess)."""
    low_flows = {
        "Ottawa River": ProvenancedValue.from_document(0.2, "cfs", citation="Ottawa 7Q10"),
        "Dug Run": ProvenancedValue.from_document(0.78, "cfs", citation="Dug Run 7Q10"),
    }
    acute_low_flows = {
        "Ottawa River": ProvenancedValue.from_document(0.0, "cfs", citation="Ottawa 1Q10"),
        "Dug Run": ProvenancedValue.from_document(0.6, "cfs", citation="Dug Run 1Q10"),
        # Deliberately no acute entry for Pike Run below.
    }
    balance = WaterBalance(
        nodes=[
            _wwtp("ott", "Ottawa WWTP", "Ottawa River", 4.0),
            _wwtp("dug", "Dug WWTP", "Dug Run", 1.0),
            _wwtp("pike", "Pike WWTP", "Pike Run", 2.0),
        ],
        warnings=[],
    )
    low_flows["Pike Run"] = ProvenancedValue.from_document(0.03, "cfs", citation="Pike 7Q10")
    checks = {c.discharger: c for c in check_assimilative(balance, low_flows, acute_low_flows)}

    # Ottawa: cited 1Q10 = 0 → 0:1 acute ratio, no acute assimilative capacity (violation).
    ott = checks["Ottawa WWTP"]
    assert ott.acute_low_flow is not None and ott.acute_low_flow.value == 0.0
    assert ott.acute_dilution_ratio == 0.0
    assert ott.acute_flag == "violation"

    # Dug Run: acute ratio = 0.6 / 1.0, matched to the 1Q10, distinct from the 7Q10 chronic ratio.
    dug = checks["Dug WWTP"]
    assert dug.acute_dilution_ratio == pytest.approx(0.6 / 1.0)
    assert dug.acute_flag == dilution_flag(0.6 / 1.0)
    assert dug.dilution_ratio == pytest.approx(0.78 / 1.0)  # chronic still on the 7Q10

    # Pike Run: no cited 1Q10 → the acute pair is left unset, never guessed.
    pike = checks["Pike WWTP"]
    assert pike.acute_low_flow is None
    assert pike.acute_dilution_ratio is None and pike.acute_flag is None

    # An acute violation registers as a not-ok finding even where it is the only violation.
    findings = {f.subject: f for f in assimilative_findings(list(checks.values()))}
    assert findings["Ottawa WWTP -> Ottawa River"].ok is False


def test_load_acute_low_flows_reads_cited_1q10_from_context(hydro_settings: Settings) -> None:
    """The acute loader lifts each stream's cited 1Q10 from the low-flow table's context block —
    including the Ottawa's honest 0 cfs — and omits streams whose fact sheet gives no 1Q10."""
    acute = lowflow.load_acute_low_flows(settings=hydro_settings)
    assert "ottawa river" in acute
    assert acute["ottawa river"].value == 0.0  # a cited 0, kept (not treated as missing)
    assert acute["ottawa river"].source == "document"
    assert acute["dug run"].value == pytest.approx(0.6)


def test_baseline_credits_lima_effluent_into_shawnee_dilution(hydro_settings: Settings) -> None:
    """On the real Lima loop, Shawnee II discharges into the effluent-laden Ottawa: crediting the
    City of Lima WWTP's ~28.6 cfs standing effluent lifts its 0.04:1 natural ratio into the tight
    band (~6.2:1). The tributary-only American II (Dug Run) has no co-reach effluent to credit."""
    _balance, checks, _findings = run_baseline(settings=hydro_settings, live=True)
    shawnee = next(c for c in checks if "Shawnee" in c.discharger)
    assert shawnee.receiving_water == "Ottawa River"
    assert shawnee.flag == "violation"  # conservative default unchanged
    assert shawnee.upstream_returns is not None
    assert shawnee.upstream_returns.value == pytest.approx(28.62, abs=0.1)  # Lima WWTP 18.5 MGD
    assert shawnee.effluent_credited_ratio is not None
    assert shawnee.effluent_credited_ratio > 1.0
    assert shawnee.effluent_credited_flag == "tight"

    dug = next(c for c in checks if c.receiving_water == "Dug Run")
    assert dug.upstream_returns is None and dug.effluent_credited_ratio is None


def test_balance_locks_bracketed_campus_consumptive(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An undisclosed cooling method is a bracket, never a single headline (CLAUDE.md). When
    # the campus basis is bracketed, the balance carries NO scalar consumptive and says so —
    # it must not leak the evaporative envelope as a headline through the data tier.
    unknown = derive_cooling_basis(cooling_model="unknown")
    assert unknown.is_bracketed
    monkeypatch.setattr(bal, "derive_cooling_basis", lambda *a, **k: unknown)
    balance = bal.build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is None
    joined = " ".join(balance.warnings).lower()
    assert "undisclosed" in joined and "bracket" in joined


def test_abstraction_node_is_profile_driven(hydro_settings: Settings) -> None:
    # The intake node identity comes from the active SiteProfile (#1159). A non-Lima site
    # with no configured abstraction node omits the reach rather than labeling its gage as
    # Lima's WTP — so no "lima-wtp" literal leaks under a second --site.
    fs = hydro_settings.model_copy(update={"site": "findlay"})
    balance = build_water_balance(settings=fs, live=True)
    assert balance.node("lima-wtp") is None
    assert not any(n.node.role == "abstraction" for n in balance.nodes)
    assert any("no abstraction node configured" in w for w in balance.warnings)


def test_water_balance_is_an_inventory_not_a_self_closing_check(hydro_settings: Settings) -> None:
    # WS-05 (#1605): the per-node WaterBalance is an inventory of grounded discharges, not
    # a self-closing balance. The old WaterBalance.closes() was vacuous — no assembled node
    # ever held both `inflow` and `return_flow`, so its loop `continue`d on every node and
    # it returned True unconditionally, was never called, and was never asserted. It is
    # gone; guard against reintroducing a self-test that cannot fail.
    balance = build_water_balance(settings=hydro_settings, live=True)
    assert not hasattr(balance, "closes"), "vacuous WaterBalance.closes() must stay removed"
    # The precondition that made the per-node check vacuous — no node carries both an inflow
    # and a return — confirms the inventory shape the docstring now documents.
    assert not any(n.inflow is not None and n.return_flow is not None for n in balance.nodes)

    # The genuine, falsifiable mass-conservation check lives on the routed network: it routes
    # the balance's return flows through the cited confluence graph and holds only when
    # Sum(base) + Sum(gain) - Sum(applied loss) == outlet flow. Lean on it here (#1605 fix), show
    # it actually fails when the inventory is corrupted.
    from watermark.hydrology import network as net

    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    assert rn.closes
    broken = rn.model_copy(update={"outlet_cfs": rn.outlet_cfs + 5.0})
    assert not broken.closes


def test_check_skips_uncited_receiving_water(hydro_settings: Settings) -> None:
    # A receiving water with no cited 7Q10 is skipped, not invented. (All three real
    # streams are now cited, so inject a plant whose receiving water is uncited.)
    balance = build_water_balance(settings=hydro_settings, live=False)
    flows = dict(lowflow.load_low_flows(settings=hydro_settings))
    flows.pop("ottawa river", None)  # drop the Ottawa citation for this check
    checks = check_assimilative(balance, flows)
    assert "Ottawa River" not in {c.receiving_water for c in checks}
    assert assimilative_findings(checks)  # the tributary checks still produced findings


def test_wilmington_reach_is_screened_end_to_end(
    hydro_settings_for: Callable[[str], Settings],
) -> None:
    """Wilmington's balance produces a real assimilative check, not "no cited 7Q10" (#886).

    The acceptance shape of that issue: the receiving water is named, the design flow comes
    from the STRUCTURED routing table rather than a regex over watch-items prose, and the
    screen actually divides. The numbers pin the finding — at design low flow the reach below
    outfall 001 *is* the effluent, ~0.0015:1 dilution.
    """
    settings = hydro_settings_for("wilmington")
    balance = build_water_balance(settings=settings, live=False)
    plants = balance.by_role("wwtp")
    assert len(plants) == 1
    wwtp = plants[0]
    assert wwtp.node.receiving_water == "Lytle Creek"
    assert wwtp.return_flow is not None
    # 3.0 MGD from routing.yaml's structured design_flow_mgd. If this ever reads as a regex
    # fallback the citation loses the fact-sheet reference and the balance warns about an
    # "expansion" (the summary prose carries both 3.0 and 4.5 MGD).
    assert wwtp.return_flow.value == pytest.approx(4.6417, abs=1e-3)
    assert "1PD00013" in (wwtp.return_flow.citation or "")
    assert not [w for w in balance.warnings if "expansion" in w]

    checks = check_assimilative(
        balance,
        lowflow.load_low_flows(settings=settings),
        lowflow.load_acute_low_flows(settings=settings),
    )
    assert len(checks) == 1
    check = checks[0]
    assert check.design_low_flow.value == pytest.approx(0.0068)
    assert check.design_low_flow.source == "derived"  # never presented as fact-sheet cited
    assert check.dilution_ratio == pytest.approx(0.00146, abs=1e-4)
    assert check.flag == "violation"
    # The finding must survive rendering: at this magnitude two decimals round the 7Q10 up by
    # 47% and the ratio to a flat "0.00:1", which reads as no measurement at all.
    assert "0.0068 cfs" in check.detail
    assert "0.0015:1" in check.detail
