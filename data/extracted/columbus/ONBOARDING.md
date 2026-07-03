# Onboarding — Columbus (columbus)

Living record for the Columbus watershed point (basin: scioto), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

Columbus / Franklin County is the **Scioto mainstem metro core** (Scioto epic #484, onboarding #486) — the largest municipal water user in the basin and **AEP's HQ city**. Receiving water = the **Scioto River** (the Olentangy joins downtown; Big Walnut + the Darby Creeks nearby); supply is a **managed metro** system — the **O'Shaughnessy / Hoover / Griggs upground reservoirs + well fields**, *not* a sole-source headwater (the inverse of the Miami buried valleys). Sink = the Ohio River at Portsmouth. Grid is the **PJM AEP** zone (AEP Ohio / Ohio Power #14006), AEP HQ being Columbus — the load that drives the contested **AEP Ohio data-center tariff** (PUCO).

## Dimension coverage

- [x] **Hydrology** — corridor-DDF + climatology ran (cited). The **Scioto-basin 7Q10s are derived** (`low-flow-7q10.derived.yaml`): Scioto River 515.73 cfs (03234500, the mouth-ward proxy), Olentangy 13.53 (03226800), Big Walnut 35.43, Big Darby 11.24. The metro abstraction/supply pair is **Scioto at Columbus (03227500)** + **Olentangy near Worthington (03226800)** — note 03227000 (Olentangy at Columbus) carries no discharge record and is not used. SSURGO skipped (no footprint → HSG C is `[inference]`). **Basin-screen is 0/0 pending the Scioto ECHO inventory** — the `watermark npdes --basin scioto` pull was deferred at onboard time (ECHO 429 throttle); rerun to populate it.
- [x] **Economics** — county baseline (Franklin 39049) + consumer-energy (OH) + **grid-profile** ran (grid-profile **succeeded** on the pinned AEP utility #14006). RSEI toxics ran (Franklin Co, 167 facilities / 132 scored — the network's largest toxics inventory; top by modeled Score: Akzo Nobel Coatings). Franklin County is the state-capital metro — the metro-scale economic comparator to the small-city nodes.
- [~] **Data-center activity** — discover-and-pin sweep + self-research first pass **done** (manifest under `data/research/onboard-columbus-...`; register in [`data-centers.md`](data-centers.md)). **Verified (Franklin County proper):** the AWS Hilliard cluster (158-genset air PTI), an AEP/Bloom **228-fuel-cell behind-the-meter plant** (73 MW, OPSB-approved, Hilliard appealing), Google "Hartman Farm" ($300M, Columbus abatement), AWS Dublin, Cologix colo. **Regulatory spine:** the **AEP Ohio data-center tariff** (PUCO 24-508-EL-ATA — 85% take-or-pay, ≥25 MW; OMA appeal at the Ohio Supreme Court). Boundary held: the New Albany/Licking epicenter is #485, not here. **Still `[open]`:** ingest the instruments (PUCO docket, air PTIs, abatement ordinance, deeds) — see `data-centers.md`.
- [~] **Per-jurisdiction GIS** — parcels = the OGRIP Ohio statewide layer scoped to Franklin (the Franklin County Auditor also hosts a fuller native owner+CAMA layer — a follow-up upgrade). Zoning = the verified City of Columbus "All Base Zoning" REST (polygon-only district catalog, city limits only); flood = national NFHL (wired). `gis_zoning` schema-wiring deferred.

## Last onboard run (2026-06-22)

| step | status | output |
|---|---|---|
| scaffold | ok | per-site dirs + READMEs |
| derive-low-flows | ok | low-flow-7q10.derived.yaml — Scioto mainstems added (Scioto 515.73, Olentangy 13.53, Big Walnut 35.43, Big Darby 11.24) |
| corridor-ddf | ok | reference/hydrology/columbus/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/columbus/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/columbus/nasa-power-climatology.yaml |
| basin-screen | skipped | 0/0 — the Scioto ECHO inventory is not yet pulled (ECHO 429 at onboard time) |
| econ-baseline | ok | reference/economics/columbus/baseline.yaml (Franklin 39049) |
| rsei | ok | reference/rsei/columbus/inventory.yaml — 167 facilities (132 scored) |
| consumer-energy | ok | reference/eia/columbus/consumer-energy.yaml |
| grid-profile | ok | reference/eia/columbus/grid-profile.yaml (AEP Ohio #14006 — pinned) |

## Open follow-ups

- **Pull the Scioto ECHO inventory** — `watermark npdes --basin scioto` (deferred on a 429 throttle) → commit `scioto-wwtp.potw.yaml` and re-run the basin-screen. Columbus's Scioto-River reach + the metro WWTPs (Jackson Pike / Southerly → Scioto) are covered by the Scioto inventory.
- **`plant_receiving`** — seed the Columbus WWTPs (Jackson Pike + Southerly → Scioto River) from their NPDES fact sheets (the permit-ID-to-plant mapping `4PF00000`/`4PF00001` needs Ohio EPA eDoc confirmation).
- **Data-center first pass** — run `--research`; track the Columbus-metro cluster + the AEP tariff exposure.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. (HSG C is `[inference]`; footprint needed.)
- [ ] basin-screen coverage is sane for this site's receiving waters. (**Pending the Scioto ECHO inventory pull — `watermark npdes --basin scioto`.**)
- [ ] A per-jurisdiction County/City GIS connector exists. (Parcels = OGRIP-Franklin; zoning = City of Columbus REST, schema-wiring deferred.)
- [x] Self-research first pass reviewed (`--research` run 2026-06-22 + a web discover-and-pin sweep; register in `data-centers.md`). Primary-instrument ingestion (PUCO docket / air PTIs / abatement / deeds) is the open residual.
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'columbus' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
