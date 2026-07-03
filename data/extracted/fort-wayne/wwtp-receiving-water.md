# Fort Wayne WWTP (NPDES IN0032191) — receiving-water characterization

Reviewed synthesis of the basin's largest POTW against its low-flow receiving water, resolving
issues **#358** (the 7Q10 denominator) and **#359** (the NPDES/DMR/enforcement extract). Tags
follow the project vocabulary (`[verified]` / `[inference]` / `[reference]` / `[open]`).

Sources, all regenerable:

- Reported effluent record (DMR): [`wwtp-in0032191.dmr.yaml`](wwtp-in0032191.dmr.yaml) —
  `watermark dmr IN0032191 --start 2023-01-01 --end 2023-12-31 --design-flow 74.0`.
- Derived headwaters 7Q10: `data/reference/hydrology/low-flow-7q10.derived.yaml`
  ("maumee river (fort wayne headwaters)") — `watermark derive-low-flows`.
- ECHO inventory entry: `data/reference/echo/maumee-wwtp.potw.yaml` (IN0032191).

## 1. The facility

| Field | Value | Tag |
|---|---|---|
| Permit | NPDES **IN0032191**, individual, **major** | `[verified: ECHO]` |
| Operator / status | Fort Wayne WWTP — permit **Admin Continued** | `[verified: ECHO]` |
| Design flow | **74.0 MGD** (≈ 114.5 cfs) — the basin's largest single POTW | `[verified: ECHO]` |
| Immediate receptor | **Baldwin Ditch** (ungaged) → Maumee R. at the St. Joseph/St. Marys headwaters | `[verified: ECHO]` |
| Outfalls | 1 continuous effluent (001) + **39 CSO/bypass outfalls** — a combined-sewer system | `[verified: ECHO DMR]` |

## 2. Actual discharge vs. permitted design `[verified: ECHO DMR, 2023]`

The 12 reported monthly-average flows at the primary outfall (001, parameter 50050) for calendar
2023:

- **mean 43.87 MGD** (≈ 67.9 cfs), min 30.3 (Nov), max 79.3 (Mar)
- **≈ 59% of the 74.0 MGD permitted design flow**

So the design flow is a conservative (worst-case) screening denominator: the plant runs at roughly
three-fifths of its permitted maximum on an annual-average basis. The design-flow screen overstates
present-day loading — a point the receiving-water verdict below turns on.

## 3. The corrected low-flow denominator (#358) `[derived]`

The Fort Wayne WWTP discharges at the Maumee **headwaters**, where the mainstem is formed by the
junction of the St. Joseph and St. Marys rivers. The right low-flow denominator is the 7Q10 **at the
headwaters**, derived from the two near-Fort-Wayne gages:

| Component | Gage | 7Q10 (cfs) |
|---|---|---|
| St. Joseph River near Fort Wayne, IN | USGS 04180500 | 54.06 |
| St. Marys River near Fort Wayne, IN | USGS 04182000 | 15.65 |
| **Maumee headwaters (sum)** | 04180500 + 04182000 | **69.71** |

LP3 over the 1980–2024 daily record (40 complete climatic years), `source=derived`, `confidence=low`
— the sum is **conservative** (the two tributaries' annual 7-day minima need not coincide, so the
true confluence 7Q10 is ≥ this sum).

### Screen against the corrected denominator

| Discharge basis | cfs | dilution (7Q10 ÷ discharge) | band |
|---|---|---|---|
| Design 74.0 MGD | 114.5 | **0.61 : 1** | **violation** (effluent-dominant) |
| Actual 43.9 MGD (2023 mean) | 67.9 | **1.03 : 1** | **tight** (effluent-balanced) |

**Verdict:** at the headwaters, the Fort Wayne WWTP is effluent-balanced-to-dominant at low flow — its
permitted maximum (0.61 : 1) would dominate the receiving water's 7Q10, and even its realistic annual
flow (≈ 1.0 : 1) roughly equals it. This is a materially significant low-flow assimilative situation,
consistent with the basin-screen thesis that the basin's largest discharger sits in tight water.

## 4. Two corrections to the onboarding hypothesis

1. **The basin-screen never used the Waterville proxy for this plant.** #358's premise — that Fort
   Wayne was screened against the downstream Waterville 7Q10 (114 cfs) — is **refuted**. Its primary
   receiver is **Baldwin Ditch**, an ungaged ditch with no 7Q10, so `watermark basin-screen` correctly
   leaves it **unscreened** (`no_7q10`) under the omit-don't-guess discipline — it is never credited
   with a downstream river's larger 7Q10. The derived headwaters 7Q10 above is a **documented
   at-mainstem proxy** for this manual characterization, deliberately *not* auto-applied to a Baldwin
   Ditch discharger (its aliases exclude the bare "maumee river"). `[verified]`
2. **The onboard log's "1 violation" is not Fort Wayne.** The basin-screen records 7/129 screened
   (1 violation, 2 tight); the single violation is **AMERICAN-BATH WWTP → Pike Run** (a Lima-loop
   plant, 0.01 : 1), not IN0032191. **Refuted.** `[verified]`

The research findings' figure of "~45 cfs / ~2.5 : 1 effluent-dominant" used the **upstream** St.
Joseph gage at Newville (04178000, 7Q10 29.69) — far above Fort Wayne. The correct near-Fort-Wayne
gage (04180500) carries 54.06 cfs, giving the milder (but still effluent-balanced) verdict above. That
upstream-gage error is exactly the denominator mistake #358 set out to fix. `[inference → verified]`

## 5. Compliance `[open — reconciliation item]`

The ECHO **DMR record shows no monthly-average effluent exceedance** in 2021–2025 (the primary
outfall's reported flows are well within the permitted range; no parameter carries an
`ExceedencePct`). Yet the ECHO inventory carries a facility-level SNC label "Effluent – Monthly
Average Limit" + 1 informal enforcement. The label is therefore **not corroborated by a recent
monthly-average exceedance** in the committed DMR window — it is most likely historical (pre-2021) or
computed from a source the effluent chart does not expose. Recorded as an open reconciliation item;
no triggering parameter is asserted (prefer omission over invention).

## 6. Open

- The CSO/combined-sewer dimension (39 overflow outfalls) is wet-weather, distinct from the continuous
  effluent screened here; not characterized. `[open]`
- A cited regulatory 7Q10 / WLA for IN0032191 (the IDEM permit fact sheet) would replace the derived
  headwaters proxy with a `source=document` value. `[open]`
