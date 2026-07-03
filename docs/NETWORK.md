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
dimension among several** — and most nodes are honestly *unscreened* (see below).

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
| **Lima** | Auglaize → Defiance | effluent-dominated tributary | **violation 0.01:1** | AEP Ohio (18.6¢) | −2.5% | 2.08 / 0.37 | 45 | **✔ disclosed** |
| Van Wert | Auglaize → Defiance | effluent-dominated tributary | unscreened¹ | AEP Ohio (18.6¢) | +3.7% | 3.14 / 0.09 | 14 | — |
| Findlay | Auglaize → Defiance | gaged tributary river | unscreened² | AEP Ohio (18.6¢) | −2.9% | 2.92 / 0.28 | 29 | — |
| Ottawa | Auglaize → Defiance | gaged tributary river | unscreened² | AEP Ohio (18.6¢) | +4.1% | 3.72 / 0.21 | 14 | — |
| Bryan | Tiffin → Defiance | effluent-dominated tributary | unscreened¹ | **City of Bryan (muni, 10.8¢)** | −5.1% | 4.54 / 0.19 | 35 | — |
| Fort Wayne | upper Maumee → Defiance | diluted mainstem | unscreened¹ | I&M / AEP (11.6¢) | +4.6% | 1.78 / 0.44 | 128 | — |
| Defiance | Maumee mainstem → Toledo | diluted mainstem | **tight 6.15:1** | FirstEnergy / ATSI (16.8¢) | −2.8% | 2.32 / 0.55 | 19 | — |
| Toledo | Maumee mainstem → Lake Erie | tidal / lake outlet | unscreened² | FirstEnergy / ATSI (16.8¢) | −6.4% | 1.50 / 0.49 | 117 | — |

¹ ungaged tributary / ECHO lists an outfall ditch as the primary receiver → no matchable 7Q10.
² no receiving water in the ECHO record (or the Blanchard is not in the derived 4-mainstem set).
*LQ = location quotient (county sector share ÷ national); >1 = over-represented. RSEI = scored
toxics facilities in the county (all vintages cap at 2014 — a basin-wide currency caveat). ¢/kWh =
EIA-861 bundled full-service price. Dilution ratios are screening-grade (gage proxies).*

## What the network shows

1. **Lima is the outlier in exactly one dimension: receiving-water *choice*.** It is the lone
   computed **violation** — small plants on flow-starved intermittent tributaries (Pike Run 7Q10 ≈
   the effluent). Set against Defiance's **6:1** mainstem dilution, the variable is the water, not
   the plant: Toledo (22.5 MGD) and Fort Wayne (74 MGD, the basin's largest) sit on the diluting
   mainstem/lake; Lima's *small* plants violate. Size is irrelevant.

2. **Only 2 of 8 nodes are cleanly low-flow-screenable** — the rest discharge to ungaged
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
