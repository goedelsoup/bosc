# Genset emission factors (air Tier-0)

Authoritative external emission factors for the backup-genset emissions inventory
(epic #1172, Tier-0). Read by `watermark.air.emissions`; regenerable — nothing here is
hand-fabricated.

## Files

| File | What | Source |
|---|---|---|
| `ap42-3.4.yaml` | EPA **AP-42 §3.4** uncontrolled emission factors for large (>600 hp) stationary diesel engines — the generic modeling prior. Verbatim Table 3.4-1 (gaseous) + Table 3.4-2 (particle sizing). | EPA AP-42, 5th ed., Vol. I, Ch. 3.4 (10/96). `source: reference`. |

## The two grounded sources, and how they reconcile

The genset model carries **two** emission-factor bases and reconciles them (the epic's
`#1175` acceptance):

1. **AP-42 §3.4** (this dataset) — the generic published prior for a large stationary
   diesel engine. It is `[reference]`, *not* a fact about the site's engines.
2. **The site air permit** (`data/extracted/permits/*.epa.yaml`) — the facility's own
   certified per-engine rates and synthetic-minor caps. For Lima that is OEPA Final Air
   PTI **P0138965**: per-engine NOx **75.78 lb/hr** (>25% load) and CO **17.62 lb/hr**
   for the 114 data-hall gensets, plus the 40 CFR 60 Subpart IIII **Tier-2** standards
   (PM 0.20 g/kWh, NOx+NMHC 6.4 g/kWh, CO 3.5 g/kWh).

**AP-42 is the modeling default; the permit is the cross-check.** The reconciliation is
expected to show AP-42 running *hot*: AP-42 "uncontrolled" describes a generic engine,
whereas the permitted units are modern Tier-2-certified, so AP-42 over-predicts NOx/CO
per engine-hour by a modest factor. `watermark.air.emissions.reconcile` reports that
ratio per pollutant. Neither source is fabricated — where the permit does not isolate a
pollutant (SO2, VOC as sub-1-tpy facility-wide), only AP-42 carries a per-engine factor.

## Known gaps & caveats

- **AP-42 §3.4 is a 1996 generic factor set** (ratings B–E); it over-states a Tier-2
  engine. It is a bound, not this facility's truth — the permit rates are.
- **PM2.5 is not a published AP-42 §3.4 cut.** It is derived from Table 3.4-2 (filterable
  <1µm + condensable ÷ total particulate) as a documented fraction of the Table 3.4-1
  combined PM — see `ap42-3.4.yaml` comments. Diesel PM is predominantly fine, so
  PM10 ≈ PM2.5 for these engines.
- **SO2 scales with fuel sulfur.** AP-42 SOx is per weight-% S; evaluated at the permit
  fuel spec (ULSD ≤ 15 ppm = 0.0015 wt-%), so the SO2 factor is tiny — consistent with
  the permit's `< 1 tpy` facility-wide SO2.
- Site-agnostic: the per-engine rating (MW) and the permit rates come from the active
  site's profile / permit extraction, **never** hardcoded to Bistrozzi/Lima.

## Regenerate

The AP-42 table is a static published document — re-transcribe from the cited PDF if the
EPA revises §3.4. It is not connector-fetched (no API); the URL in `ap42-3.4.yaml` is the
canonical source.
