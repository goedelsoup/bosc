# The BOSC network — Maumee watershed points as one connected basin

The platform onboards each watershed point independently, but the points are **not** parallel,
independent sites: every one drains to the **same Maumee → Lake Erie system** under the **same**
2023 Maumee Watershed Nutrient TMDL phosphorus cap. They are nested nodes on one basin — exactly
the Allen County two-river logic (Auglaize in, Ottawa out) scaled to the whole network. So a
data-center sanitary/nutrient load at *any* node accumulates downstream into one fully-allocated,
Lake-Erie-bound budget.

This page is authored from the output of `watermark basin-network` (computed by
[`watermark.network`](../src/watermark/network.py); `--write` persists the
[`basin-network.yaml`](../data/reference/network/basin-network.yaml) artifact, not this
doc) over the curated topology
([`data/reference/network/topology.yaml`](../data/reference/network/topology.yaml))
and each node's own committed economy / grid / toxics artifacts. The dilution screen is **one
dimension among several** — and half the nodes are honestly *unscreened* (see below).

## Basin topology — the loads converge downstream

```text
Lake Erie  ←  Toledo  ←─ Lower Maumee ──  Defiance ─┬─ Auglaize ←─ Lima · Van Wert · Findlay · Ottawa
            (tidal outlet)                (confluence)├─ Tiffin   ←─ Bryan
                                                      └─ Upper Maumee ←─ Fort Wayne
```

**Defiance sits at the Maumee/Auglaize/Tiffin confluence and Toledo at the tidal outlet — so they
are downstream of nearly everything.** A load at Lima, Van Wert, Findlay, Ottawa (Auglaize subtree),
Bryan (Tiffin), or Fort Wayne (upper Maumee) passes through Defiance → Toledo into Lake Erie.

## Cross-site scorecard

| Node | Subtree → down | Receiving-water regime | Low-flow screen | Serving utility (¢/kWh) | County jobs Δ | mfg / info LQ | RSEI | DC |
|---|---|---|---|---|---|---|---|---|
| **Lima** | Auglaize → Defiance | effluent-dominated tributary | **violation 0.01:1** | AEP Ohio (18.6¢) | −0.2% | 2.15 / 0.00 | 49 | **✔ disclosed** (275 MW) |
| Van Wert | Auglaize → Defiance | effluent-dominated tributary | **violation 0.03:1** | AEP Ohio (18.6¢) | +3.7% | 3.14 / 0.09 | 15 | **✔ disclosed** (500 MW) |
| Findlay | Auglaize → Defiance | gaged tributary river | **violation 0.009:1**³ | AEP Ohio (18.6¢) | −2.9% | 2.92 / 0.28 | 29 | **✔ disclosed** (150 MW) |
| Ottawa | Auglaize → Defiance | gaged tributary river | unscreened²’³ | AEP Ohio (18.6¢) | +4.1% | 3.72 / 0.21 | 15 | — |
| Bryan | Tiffin → Defiance | effluent-dominated tributary | unscreened¹ | **City of Bryan (muni, 10.8¢)** | −5.1% | 4.54 / 0.19 | 40 | — |
| Fort Wayne | upper Maumee → Defiance | diluted mainstem | unscreened¹ | I&M / AEP (11.6¢) | +4.6% | 1.78 / 0.44 | 140 | **✔ disclosed** (90 MW) |
| Defiance | Maumee mainstem → Toledo | diluted mainstem | **tight 6.15:1** | FirstEnergy / ATSI (16.8¢) | −2.8% | 2.32 / 0.55 | 19 | — |
| Toledo | Maumee mainstem → Lake Erie | tidal / lake outlet | unscreened² | FirstEnergy / ATSI (16.8¢) | −6.4% | 1.50 / 0.49 | 124 | — |

¹ ungaged tributary / ECHO lists an outfall ditch as the primary receiver → no matchable 7Q10.
² no receiving water in the ECHO record.
³ **Blanchard River — the low flow at every gage below Findlay is REGULATED, not natural** (#1458).
Findlay screens against Ohio EPA's own at-outfall design 7Q10 (0.21 cfs at RM 56.42, fact sheet
2PD00008\*UD Table 12), not the derived 8.67 cfs at USGS 04189000: that gage is downstream of the
plant's own outfall and downstream of the Findlay Reservoir low-flow augmentation return. Where the
Blanchard is unregulated, USGS publishes a 7Q10 of 0-0.03 cfs. See
`data/reference/network/findlay-ottawa-comparison.yaml`.
*LQ = location quotient (county sector share ÷ national); >1 = over-represented. RSEI = TRI/RSEI
reporting facilities in the county, **EPA RSEI v2.3.12 (TRI reporting years 1988–2022)** — one
vintage network-wide, so the counts are cross-site comparable (#436). ¢/kWh = EIA-861 bundled
SSO-cohort price. Dilution ratios are screening-grade (gage proxies). DC MW is disclosed IT load.*

## What the network shows

1. **Receiving-water *choice* is the variable, not plant size.** Three of the four screenable
   nodes compute a **violation**: Lima **0.01:1** (18.5 MGD into an Ottawa River 7Q10 of 0.20 cfs),
   Van Wert **0.03:1** (4.0 MGD into Town Creek's 0.16 cfs), Findlay **0.009:1** (15.0 MGD into the
   0.21 cfs Ohio EPA states at its outfall). Set against **Defiance's 6.15:1** — a *larger* 12.0 MGD plant that clears,
   because it discharges to a 114 cfs Maumee mainstem — the ranking is by receiver, not by plant:
   Van Wert's 4 MGD violates where Defiance's 12 MGD does not. Size is not the variable; the water
   is.

   The two **largest** dischargers in the basin — Fort Wayne (74 MGD) and Toledo (22.5 MGD) — are
   **unscreened**, not passing: ECHO carries no receiving water for either, so neither can be read
   either way. That is a gap in the record, not a clean result.

2. **Only 4 of 8 nodes are cleanly low-flow-screenable** — the rest discharge to ungaged
   tributaries or carry no receiving water in ECHO. The data gap is itself a finding: the basin is
   under-monitored, and a defensible basin-wide answer needs each tributary's own cited/gaged 7Q10
   (tracked in the per-site onboarding sub-issues).

3. **The economic shape is universal, not a Lima quirk.** Every node is a **manufacturing-
   concentrated** county (mfg LQ 1.5–4.5) with a **near-absent information sector** (info LQ
   0.09–0.55, all < 1). The boom's "regulated compute load, not jobs, onto a shrinking industrial
   base" lands the same way across the whole network.

4. **The grid is where the nodes genuinely differ:** AEP Ohio's bundled SSO (~18.6¢) vs Indiana &
   Michigan Power (~11.6¢) vs FirstEnergy/ATSI (~16.8¢) vs Bryan's **municipal** system (~10.8¢, the
   network's only non-IOU). The energy-cost structure a data center would face is node-specific.

5. **One shared sink, one shared cap.** All eight drain to Lake Erie under one TMDL phosphorus
   budget (future-growth reserve ~1.4–1.5 mt P/spring). A new sanitary load anywhere upstream
   accumulates through Defiance → Toledo into the *same* fully-allocated basin — the connectivity is
   the point.

See also [the bigger picture](bigger-picture.md) (where Lima is typical vs the outlier) and the
committed comparison artifact [`data/reference/network/basin-network.yaml`](../data/reference/network/basin-network.yaml).
