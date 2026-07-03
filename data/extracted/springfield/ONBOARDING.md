# Onboarding — Springfield (springfield)

Living record for the Springfield watershed point (basin: great-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

Springfield is the network's **second Miami-basin site** (epic #451 / onboarding #452): the **Mad River mid-corridor** node — ~20 mi downstream of the Urbana headwaters (#441) and ~25 mi upstream of Dayton / Wright-Patterson AFB (#442) — on the same **Mad River buried-valley sole-source aquifer** (US-EPA designated; the Springfield municipal **well field** is the textbook draw on that outwash sand & gravel). What distinguishes it from headwater Urbana is a **second, managed supply water**: Buck Creek, regulated by USACE **C.J. Brown Reservoir** — a two-source, partly-impounded hydrology versus Urbana's single free-flowing reach. The geology is the deliberate **inverse** of the Maumee lake-plain sites (groundwater-dominated HSG B vs. poorly-drained Black Swamp clays HSG D; sink = Ohio River, not Lake Erie; no Maumee-style nutrient TMDL).

## Dimension coverage

- [x] **Hydrology** — corridor-DDF + climatology connectors ran (Springfield-specific, cited).
  **Receiving-water screen now real (#455 / #445 / #446):** the **Mad River 7Q10 is derived** at
  USGS 03269500 (Springfield reach) = **166.55 cfs** in `low-flow-7q10.derived.yaml`, and the
  basin-screen runs against a committed **Great Miami** ECHO inventory (`great-miami-wwtp.potw.yaml`,
  81 POTW) — **14 screened**, replacing the meaningless Maumee 7/129. The distinguishing **Buck Creek
  / C.J. Brown Reservoir** second supply has **no derivable discharge 7Q10** — gage 03268100 is a
  reservoir-release / stage gage with no daily-discharge record (1980-2024) — recorded as a finding.
  SSURGO still skipped (no footprint → HSG B stays `[inference]`).
- [x] **Economics** — county baseline + consumer-energy ran (high-confidence: Clark Co). RSEI toxics ran (Clark Co, 35 facilities / 28 scored; top by modeled Score: International Steel Wool). grid-profile ran on the now-pinned serving utility **Dayton Power & Light** (AES Ohio, EIA-861 #4922; PJM/PUCO) — verified from the EIA-861 2024 Service_Territory: Clark Co is DP&L/Duke/Ohio-Edison, no AEP.
- [~] **Data-center activity** — self-research first pass (#247) found `[verified]` **zero** Springfield
  primary documents in the corpus. The follow-up discover-and-pin sweep (#454) found the activity is
  **real and pinnable** — recorded in [`data-centers.md`](data-centers.md): **5C Data Centers / Vultr**
  at PrimeOhio (601 Benjamin Drive — 150 MW, closed-loop, up to **300k gal/day** permitted municipal
  water) + a separate **Crusoe** build (75 MW), both with state/city subsidy instruments; the giant
  "New Carlisle" hyperscale story is **Indiana**, not Clark County (guardrail). The Roshel / International
  Motors "Springfield APA" prose note is **scoped out** (#453) — an armored-vehicle plant Asset Purchase
  Agreement, no data-center link; it stays a quarantined out-of-graph note. **Still `[open]`:** the primary
  instruments (air PTI, SOS, deed, EZ/TCA) are listed in `data-centers.md` but not yet ingested.
- [ ] **Per-jurisdiction GIS** — Clark County parcels / City of Springfield zoning connector (the known lift; see docs/onboarding.md). Flood = national NFHL (wired).

## Last onboard run (2026-06-21, `--research`)

| step | status | output |
|---|---|---|
| scaffold | ok | per-site dirs + READMEs |
| derive-low-flows | ok | low-flow-7q10.derived.yaml — now **includes Mad River 166.55 cfs (03269500)** + Great Miami River 407.67 (03274000) (#455/#445) |
| corridor-ddf | ok | reference/hydrology/springfield/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/springfield/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/springfield/nasa-power-climatology.yaml |
| basin-screen | ok (Great Miami) | **14/81 POTW** screened vs Mad River + Great Miami 7Q10 (`great-miami-wwtp.potw.yaml`, #446/#455) |
| econ-baseline | ok | reference/economics/springfield/baseline.yaml |
| rsei | ok | reference/rsei/springfield/inventory.yaml — 35 facilities (28 scored) |
| consumer-energy | ok | reference/eia/springfield/consumer-energy.yaml |
| grid-profile | ok | reference/eia/springfield/grid-profile.yaml — Dayton Power & Light #4922, PJM |
| self-research | ok | research/onboard-springfield-springfield-data-center-acti-2026-06-21/ |

## Self-research (Phase 5; #247) — 2026-06-21

`watermark onboard springfield --research` (claude-opus-4-8, 13 turns, $0.53). Findings + manifest in
`data/research/onboard-springfield-springfield-data-center-acti-2026-06-21/`.

**Bottom line.** Springfield is scaffolded but **not promotable** — both load-bearing dimensions
are open: the data-center dimension is the **barest in the network** (a single quarantined
corridor-context note, no primary record), and the receiving-water screen has **no Mad-River
denominator** (same hole as Urbana).

- **Data-center activity — `[open]`, no primary record (and one quarantined note).** `[verified]`
  there are **zero** Springfield/Clark-County primary documents in the corpus — no deed, NPDES,
  SOS shell, CRA/PILOT, or zoning instrument; nothing in the entity graph. The single in-corpus
  signal is `docs/COURSE.md`'s **Roshel / International Motors (Springfield APA, 2026-03-30)**
  note, logged **strictly as corridor context, not a connection** — it is explicitly *not* linked
  to BOSC and **must not enter the entity graph**. **Method note:** the Lima/Allen Bistrozzi
  land-assembly graph is **not** bridged in (no evidentiary link); any Springfield land assembly
  stays a separate register, and the Roshel note stays quarantined until pinned to a filed
  instrument.
- **Receiving-water screen — empty.** `receiving_water_name` is the Mad River `[verified]`
  (the Springfield WRF reach), but it is in **neither** 7Q10 table (cited = the three Lima
  streams; derived = the four Maumee mainstems), and the only committed ECHO inventory is
  Maumee-scoped. The "7/129 screened" basin-screen is the **Maumee** inventory — it does not
  cover the Great Miami / Ohio-River basin. The Mad River **is gaged at Springfield (03269500)**
  and upstream at Eagle City (03267900), so a derived 7Q10 is obtainable — the denominator is
  missing, not impossible.
- **The screen is a *source-water / abstraction* screen, with a two-source twist.** Like Urbana,
  Springfield's thesis is **consumptive cooling draw vs. Mad River baseflow + the sole-source
  buried-valley aquifer**, not Lima's effluent-vs-tiny-7Q10. Unlike Urbana, Springfield has a
  **second, USACE-managed supply** (Buck Creek / C.J. Brown Reservoir, gage 03268100) — the
  screen must reflect the managed/impounded source, not copy a single-reach denominator.
- **Grid is now pinned — no AEP/DAY seam.** The "AEP/DAY seam" premise is **stale**: verified from
  the EIA-861 2024 Service_Territory, Clark County is served by **Dayton Power & Light** (AES Ohio,
  EIA-861 #4922) / Duke Energy Ohio / Ohio Edison — **with no AEP**. grid-profile is pinned on DP&L
  #4922, PJM/PUCO (Ohio, so the cross-state connector axis isn't re-triggered). A *different* zone than
  Urbana here would itself be a finding (the "complex mix of influences" thesis).
- **Watershed-axis concern raised by the agent is already resolved.** The run (working from a
  read-only Lima-bound view) flagged a possible "Maumee-axis mismatch" and proposed escalating it.
  That premise is **stale**: the network is deliberately multi-basin — the Maumee lake-plain branch
  alongside the Great Miami buried-valley branch opened with Urbana (#440/#451). Springfield/Clark-Co →
  Mad River → Great Miami → Ohio River is the *intended* placement, not a mismatch — no escalation
  needed.

**Proposals — triaged.** Of the run's 5 drafts, two are **resolved by this onboarding** (disambiguate
"Springfield" → Clark County OH, Great Miami; register the `SiteProfile`) and one is **moot** (the
watershed-axis escalation — see above), so they are recorded here rather than filed. The genuinely-open
work is filed as sub-issues of #452: source-or-scope the Roshel/International Motors APA thread;
discover/pin Clark County (New Carlisle ↔ Springfield I-70) data-center activity; the Springfield WRF
NPDES + Mad-River-at-Springfield 7Q10 (with #445/#446); and ~~pin the Clark County utility + PJM zone~~
(**done** — DP&L/AES Ohio #4922, PJM/PUCO, verified from EIA-861 2024 Service_Territory; no AEP).

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. (HSG B is `[inference]`; footprint needed.)
- [x] basin-screen coverage is sane for this site's receiving waters. (**Great Miami inventory + Mad River 7Q10 committed; 14/81 screened (#446/#455). The Springfield WWTP itself is unscreened — ECHO carries no receiving water for it — exactly like Lima WWTP.**)
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (Phase 5, 2026-06-21; data-center = barest leg, receiving-water screen empty; proposals triaged — 4 filed as sub-issues of #452, 3 resolved/moot recorded above).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'springfield' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
