# Wilmington Low-Flow Screen — Two Water Threads, One Effluent-Dominated Reach

The **defining Wilmington receiving-water problem** (#516 / #886 / #1472). Status **as of
2026-08-05**; supersedes the 2026-07-03 version of this document.

**2026-08-05 (#886):** the §2.5 outfall-reach statistic stopped being a manual characterization and
became a **committed screening denominator** — `hydrology_balance` and `hydrology_scenario` now
both return real results for this site instead of "no cited 7Q10". Nothing in §1–§2 changed; the
numbers below were independently re-derived from NWIS and reproduce exactly. See **§3.3**.

**What changed, in one line:** the prior version of this screen was built on the premise that Todd
Fork is *ungaged*, and therefore had to be bracketed by the Little Miami mainstem gages at Milford
and Oldtown. That premise was wrong. Todd Fork **is** gaged — historically — and its own record
carries **21 complete climatic years of daily discharge**. The at-site 7Q10 is now transferred a
short way down Todd Fork itself (219 → 79 mi², a factor of **2.8**) instead of a long way off a
different river (1203 → 79 mi², a factor of **15**). The Milford/Oldtown bracket is retired as the
anchor — though Milford remains the site's live-reading gage, for reasons that are about plumbing
rather than hydrology (§3.1).

**The second correction:** this document previously mixed the City's *water supply* and the City's
*discharge* into a single "Wilmington water" screen. They are unrelated waterbodies with unrelated
governing instruments, and one of them is not a low-flow problem at all. They are separated below.

---

## The two threads

| | **Thread A — withdrawal** | **Thread B — effluent** |
|---|---|---|
| Waterbody | **Caesar Creek Lake** (impounded) | **Lytle Creek → Todd Fork** (free-flowing) |
| Basin position | Little Miami tributary, *west* of the city | Little Miami tributary, *through* the city |
| Governing instrument | 1970 USACE ↔ ODNR storage contract | NPDES OH0028134 / 1PD00013\*QD |
| Binding constraint | **contracted storage volume** | **assimilative capacity at design low flow** |
| Is a 7Q10 relevant? | **No** — a reservoir allocation, not a flow statistic | **Yes** — this is the whole screen |
| Gage | `03242350` (stage-only today) | `03244000` (discontinued 1974; the anchor) |

**These two threads never share arithmetic.** Nothing in Thread A may be divided by a Thread B
7Q10, and no Thread B dilution ratio may be credited with Thread A supply. The *only* place they
meet is the AWS campus (§4), which draws from Thread A and sewers to Thread B.

---

## 1. Thread A — the withdrawal side (Caesar Creek Lake)

Since **1994** the City's principal raw supply is **Caesar Creek Lake**, a USACE flood-control
reservoir on Caesar Creek — a *different* Little Miami tributary from Todd Fork, joining the
mainstem well downstream of the city. `[verified — City of Wilmington, "About Water Treatment"]`

- **Allocated drinking-water storage: ~12 billion gallons** of the lake's storage.
  `[verified — City water-treatment page]`
- **Backup supply:** two City-owned **Burtonville reservoirs**, **450 MG** combined, filled by
  pumping from **Cowan Creek**. `[verified — same]`
- **Plant:** designed to produce up to **4 MGD**; currently produces **~2 MGD**.
  `[verified — same]` (An earlier "2.2–2.8 MGD average" figure is *not* on the City page and is
  **not** carried here.)
- **Finished-water storage:** towers **3.25 MG**, underground clearwells **1.385 MG**.
  `[verified — same]`
- The NPDES fact sheet independently corroborates the source: *"The City's potable water comes from
  reservoirs."* `[verified — Ohio EPA fact sheet 1PD00013.fs, 2023-05-19, p.2]`

### 1.1 — Why there is no 7Q10 here

The binding constraint on Thread A is a **contracted storage allocation in an impoundment**, not a
seven-day-ten-year low flow in a stream. At ~2 MGD against ~12 billion gallons of allocated
storage, the supply is limited by contract terms and treatment capacity, not by drought hydrology.
**Any arithmetic that screens Wilmington's withdrawal against a Todd Fork 7Q10 is a category
error.** `[inference — from the instrument type]`

Gage **`03242350` (Caesar Creek near Wellman OH**, DA 239 mi², Warren County) is the *withdrawal-side*
gage carried in the profile's `nwis_sites`, and it cannot support a low-flow statistic either:

- Daily **discharge** (parm 00060) exists only for **1965-07-01 → 1974-06-30** (3,287 days).
- Everything current is **stage** (00065, 2017-10-03 →) and water temperature (00010, 2022 →).
  There is **no** current daily-discharge record. `[verified — NWIS series catalog, 2026-08-01]`
- The 1965–74 discharge record is **pre-impoundment** — it does not describe the regulated regime
  the City actually draws from. `[inference]`

So Caesar Creek correctly remains `no_7q10` in the basin screen, and the note in
`data/reference/hydrology/mainstem-gages.yaml` saying so is accurate. It is retained.

### 1.2 — The instruments (Thread A)

1. **1970 USACE ↔ ODNR contract**, Caesar Creek Project — flood control and water supply. ODNR
   receives water-storage space; in exchange **ODNR pays the Corps 12.7% of the annual experienced
   joint-use operation-and-maintenance costs**, payable in advance each July 1 with actual costs
   readjusted annually. `[verified — Marzulla Law case summary; corroborated by Ohio Ag Net]`
   **Correction to the #1472 issue body:** the 12.7% obligation runs from **ODNR**, not the City.
   **ODNR then bills the City for reimbursement** — the City's exposure is derivative.
   `[verified — Ohio Ag Net, 2020-03-16]`
2. ***Ohio v. United States***, **U.S. Court of Federal Claims** (Judge Lettow), filed
   **2020-03-16** by AG Dave Yost; docket **20-288** (read off the court-document reference
   `2020cv0288-17-0` in the Marzulla summary — the number is *derived from that filename*, not from
   the docket itself). The Corps' 2017 audit claimed **$187,150.07** in back charges; Ohio paid
   half, then paid in full under a 1% charge plus 6% interest on amounts >90 days delinquent, then
   sued. The court **denied** the government's motion to dismiss as to breach of contract and
   illegal exaction, and **dismissed** the takings claim. `[verified — Marzulla Law]` AG Yost:
   *"Some of the receipts we have seen are unbelievable — like charges for attending a boat show."*
   `[verified — Ohio Ag Net]`

**Why this matters to the data-center question:** these instruments **price the marginal gallon** a
campus would reserve. A dispute over what the Corps may charge for joint-use O&M is a dispute over
the cost basis of every gallon Wilmington sells — including to AWS.

### 1.3 — Thread A open items

- The **contract text itself** is unpulled. `[open]` The 12.7% figure and the storage allocation
  are secondary-source here; the instrument is the primary record.
- The **7 MGD "may purchase up to"** figure asserted in the #1472 issue body is **not** on the City
  water page and is **not** carried in this document until an instrument supports it. `[open]`
- The **ODNR → City reimbursement schedule** (what the City actually pays per year). `[open]`

---

## 2. Thread B — the effluent side (Lytle Creek → Todd Fork)

### 2.1 — The discharge

**City of Wilmington WWTP**, NPDES **OH0028134 / 1PD00013\*QD**, outfall 001 to **Lytle Creek at
RM 6.83**. Constructed 1936, last upgraded 1989.
`[verified — Ohio EPA fact sheet 1PD00013.fs, 2023-05-19]`

| | current | after PTI #1543170 |
|---|---|---|
| average daily design flow | **3.0 MGD** | **4.5 MGD** |
| peak hydraulic capacity | **6.25 MGD** | **9.0 MGD** |

New limits effective **2026-03-01**; the station-602 bypass is eliminated in the expansion.
`[verified — same fact sheet]`

**Lytle Creek use designations** (OAC 3745-1-18): Warmwater Habitat (WWH), General High Quality
Water, Agricultural Water Supply, Industrial Water Supply, Primary Contact Recreation. HUC
**05090202-06-03**, Clinton County, Eastern Corn Belt Plains ecoregion.
`[verified — same fact sheet, p.2]`

Stream network: **Lytle Creek → Todd Fork → Little Miami River → Ohio River.**
`[verified — same fact sheet]`

### 2.2 — Gage resolution (the #1472 question)

**`03243150` "Todd Fork near Clarksville OH" — resolved NEGATIVE.** It cannot carry a low-flow
statistic. `[verified — NWIS site service + series catalog, 2026-08-01]`

| attribute | value |
|---|---|
| location | 39.43617239, -83.9446523 — **Clinton County**, on Todd Fork itself |
| drainage area | **56.6 mi²** |
| datum / altitude | 758.60 ft NAVD88 |
| **daily values (`dv`)** | **none** |
| **unit values (`uv`/`iv`)** | **none** |
| water quality (`qw`) | a **single sample date: 1981-08-21** (~60 parameters, one visit) |
| peak flow (`pk`) | 2 peaks, 2022-02-23 and 2023-03-25 |
| annual (`ad`) | 4 entries, 2006–2010 |

The "data back to 1981" the issue anticipated is **one water-quality visit in August 1981**, not a
record. There is **no discharge time series at this station in any form.** It is a partial-record /
water-quality site. It is **not** added to `nwis_sites`.

One thing it *does* give us, and it is valuable: a **published contributing drainage area of
56.6 mi² on Todd Fork in Clinton County**, and a *position* — navigation confirms `03243150` lies
**upstream of the Lytle Creek confluence** (NHDPlus DM chain `3932414 → 3932434 → 3932452`, which
does not include Lytle Creek's mouth reach `3932432`). So even a hypothetical gage here would
measure Todd Fork **without** the WWTP effluent. `[verified — USGS NLDI navigation, 2026-08-01]`

**`03244000` "Todd Fork near Roachester OH" — resolved POSITIVE, and it changes the method.**

| attribute | value |
|---|---|
| location | 39.3353384, -84.08660039 — Warren County, near the Todd Fork mouth |
| drainage area | **219 mi²** |
| **daily discharge (`dv` 00060)** | **1952-09-01 → 1974-10-29 — 8,094 days** |
| suspended sediment (`dv` 80154/80155) | 1952-09-01 → 1958-09-29 |
| peak flow (`pk`) | 22 peaks, 1953-01-17 → 1974-06-23 |

The reason this record was invisible to the platform is mechanical, not evidentiary:
`compute_low_flow_frequency` defaults to `start_date="1980-01-01"` — the **entire Todd Fork record
predates the derivation window**, so the gage returned empty and the reach was written up as
"ungaged." It is not ungaged. It is *historically* gaged.

### 2.3 — The anchor statistics

LP3 over the full record, computed with this repo's own `watermark.hydrology.lowflow_frequency`:

**USGS 03244000, Todd Fork near Roachester OH — 21 complete climatic years, 1952-09-01 → 1974-10-29**

| statistic | LP3 | Weibull (check) |
|---|---|---|
| 1Q10 | **0.1107 cfs** | 0.084 cfs |
| **7Q10** | **0.1654 cfs** | 0.105 cfs |
| 30Q10 | **0.6991 cfs** | 0.708 cfs |
| harmonic-mean flow | **5.7786 cfs** | (8,082 non-zero days; **12 zero-flow days excluded**) |

`[verified — record]` / `[inference — the fitted statistic]`

**21 climatic years clears the platform's `_MIN_YEARS = 20` floor for a defensible LP3 7Q10.** LP3
and Weibull agree to within a factor of 1.6 at the 7-day/10-year point — no fitting pathology.

**The 12 zero-flow days are the finding, not a footnote.** Todd Fork *stops* in drought. A 7Q10 of
0.17 cfs on a 219 mi² watershed is not a small number that happens to round low — it is a stream
that goes to zero, and the LP3 fit is merely describing that.

### 2.4 — Drainage areas (the `[open]`s, now filled)

All contributing areas pulled **2026-08-01**. The NLDI-derived areas are validated against the two
NWIS-published station areas: **57.1 vs 56.6 mi² (+0.9%)** and **219.4 vs 219 mi² (+0.2%)** — so the
method is trustworthy at the ungaged points.

| reach | NHDPlus comid | DA (mi²) | source |
|---|---|---|---|
| Lytle Creek at **WWTP outfall 001** | 3932402 | **9.0** | NLDI basin polygon `[verified]` |
| Lytle Creek at its mouth | 3932432 | **20.4** | NLDI basin polygon `[verified]` |
| Todd Fork above Lytle (Clarksville gage `03243150`) | 3932414 | **56.6** | NWIS published `[verified]` |
| Todd Fork **below** the Lytle confluence | 3932452 | **79.0** | NLDI basin polygon `[verified]` |
| Todd Fork at Roachester gage `03244000` **(anchor)** | 3935784 | **219** | NWIS published `[verified]` |
| Little Miami near Oldtown `03240000` | — | **129** | NWIS published `[verified]` |
| Little Miami at Milford `03245500` | — | **1203** | NWIS published `[verified]` |

**Correction:** the prior version of this document, and the note in `mainstem-gages.yaml`, both gave
Milford as **1664 mi²**. NWIS publishes **1203 mi²** (`drain_area_va` = `contrib_drain_area_va` =
1203). The 1664 figure was uncited and is **wrong by +38%**. It is corrected in both places. It
never entered a computation — it appeared only in prose and in a YAML `note:` field — but a DAR
divided by it would have *understated* the transferred 7Q10.

### 2.5 — The transfer

Standard USGS drainage-area-ratio transfer of a low-flow statistic within the **same stream
system** `[reference]`:

```
Q(ungaged) = Q(gaged) × ( DA(ungaged) / DA(gaged) )^b        b = 1.0
```

This is now a **short transfer down Todd Fork itself** (219 → 79 mi², a factor of 2.8) rather than
the previous long transfer from the Little Miami mainstem (1203 → ~79 mi², a factor of 15). The
gaged and ungaged reaches share climate, geology, land use and — critically — the same
intermittent-headwater low-flow behavior. `b = 1.0` is the simple DAR; a regional exponent from the
USGS Ohio low-flow report (Koltun) remains available and would move these numbers, but every value
below goes to zero for practical purposes at any plausible `b`, so the choice is not load-bearing
here. `[reference]`

**Transferred low-flow statistics — all values `[inference]`, DAR from `03244000`:**

| reach | DA (mi²) | 1Q10 | 7Q10 | 30Q10 | harmonic mean |
|---|---|---|---|---|---|
| Lytle Ck at **WWTP outfall 001** | 9.0 | 0.0045 | **0.0068** | 0.0287 | 0.237 |
| Lytle Ck at mouth | 20.4 | 0.0103 | **0.0154** | 0.0651 | 0.538 |
| Todd Fork above Lytle | 56.6 | 0.0286 | **0.0427** | 0.1807 | 1.493 |
| Todd Fork below Lytle | 79.0 | 0.0399 | **0.0597** | 0.2522 | 2.085 |
| Todd Fork at Roachester *(anchor, measured)* | 219 | 0.1107 | 0.1654 | 0.6991 | 5.779 |

All values cfs.

### 2.6 — What the transfer says: the reach is effluent

1 MGD = 1.54723 cfs. At the acute design condition (7Q10):

| WWTP flow | | at outfall 001 (DA 9.0) | below Lytle confluence (DA 79.0) |
|---|---|---|---|
| 3.0 MGD (current design) | 4.64 cfs | **99.85% effluent** | **98.73% effluent** |
| **4.5 MGD (post-expansion)** | **6.96 cfs** | **99.90% effluent** | **99.15% effluent** |
| 9.0 MGD (new peak hydraulic) | 13.93 cfs | 99.95% effluent | 99.57% effluent |

At the chronic design condition (harmonic-mean flow), 4.5 MGD is **96.7%** of the flow at the
outfall and **77.0%** below the Lytle confluence.

**The finding:** at design low flow, Lytle Creek below outfall 001 *is* the WWTP. Dilution is
**~0.001:1** — a thousand parts effluent to one part stream. Expanding 3.0 → 4.5 MGD does not
change the character of the reach because there was no dilution to lose; it changes the **load**
delivered into a stream with essentially no assimilative capacity, carrying a **Warmwater Habitat**
and **Primary Contact Recreation** designation. `[inference — from verified inputs]`

This is the same structural pattern as Lima's WWTP → Ottawa River (~98% effluent), and it is more
extreme.

### 2.7 — Two negatives worth recording

1. **The fact sheet states no receiving-water 7Q10.** It discusses assimilative capacity
   qualitatively — *"The assimilative capacity depends on the flow in the water receiving the
   discharge… The greater the upstream flow… the greater the assimilative capacity is"* — and then
   never gives the flow. There is no 7Q10, no design flow, and no dilution ratio anywhere in the
   11-page document. `[verified — exhaustive search of 1PD00013.fs.pdf, 2026-08-01]` So the
   sanity-check the prior version of this screen hoped for **does not exist**, and the figures in
   §2.5 are the only quantitative low-flow characterization of this reach in the record.
2. **Limits are technology-based, not flow-based.** The expansion's effluent limits are keyed to
   **BADCT** (Best Available Demonstrated Control Technology) and, for phosphorus, to the **2011
   Total Maximum Daily Load for the Lower Little Miami River** under an adaptive-management
   approach — a seasonal (June 1 – October 31) average daily load reported once per year.
   `[verified — same fact sheet]` **This is consistent with §2.6:** a water-quality-based limit
   requires an assimilative-capacity calculation, and on a reach with a 0.0068 cfs 7Q10 there is
   nothing to calculate. Ohio EPA regulated the technology instead.

### 2.8 — Scenic-river overlay `[reference]`

The Little Miami is a **National & State Scenic River** — the same anti-degradation overlay as
Xenia upstream. Todd Fork and Lytle Creek are *tributaries to* the designated reach, not the
designated reach itself, so the overlay binds downstream of the confluence. Its bearing on the
`passby_primary_cfs` / `passby_secondary_cfs` knobs is unresolved (§3).

---

## 3. Profile knobs

**No knob changes.** The §2.3 anchor is a *historical* record, and every one of these knobs demands
a **currently reporting** gage — see §3.1. What changes is the citations, not the values.

| knob | value | status |
|---|---|---|
| `nwis_sites` | `03245500`, `03240000`, `03242350` | unchanged — `03244000` **not** added (§3.1); `03243150` **not** added (§2.2) |
| `abstraction_gage` | `03245500` | unchanged — still the nearest *active* discharge gage, still overstates at-site flow by ~15× in DA (§3.1) |
| `supply_gage_primary` / `_secondary` | `03245500` / `03240000` | unchanged — these drive the *refill* model, a Thread A concern, and neither is the City's actual supply (§3.2) |
| `passby_primary_cfs` / `_secondary_cfs` | `0.0` / `0.0` | **`[open]`** — see §3.2 |

### 3.1 — Why Todd Fork's own gage cannot go in the profile

This is the trap, and it is worth stating plainly because the temptation to "upgrade" these knobs
to the better gage is strong and would silently break the site:

`nwis_sites`, `abstraction_gage`, `supply_gage_*` all resolve through
`watermark.hydrology.connectors.nwis.fetch_streamflow`, which calls the **instantaneous-values**
service for the *latest* reading. **`03244000` has produced no instantaneous values since 1974.**
Verified directly: an IV request for `03244000,03245500` returns **two** time series, both for
`03245500`; `03244000` returns nothing at all. `[verified — NWIS IV service, 2026-08-01]`

Setting `abstraction_gage="03244000"` would therefore hand `balance.py` an empty reading list — a
silent degradation, not a loud failure. **A gage that is excellent for a low-flow *statistic* can be
useless as a live *knob*.** The two roles are not interchangeable, and this site is where the
distinction bites.

The consequence is worth recording as a finding in its own right: **there is no currently reporting
discharge gage on Todd Fork, on Lytle Creek, or on Caesar Creek below the dam.** `03243150` is
water-quality only; `03242350` reports stage and temperature but not discharge; `03244000` has been
dark for fifty years. The nearest active discharge gage is Milford — **1203 mi² against an at-site
79.0 mi²**, a 15× overstatement of the drainage area, and it stays flagged as such.

### 3.2 — Why the passby knobs stay `[open]`, explicitly

`passby_*` are **refill-model** knobs: the minimum in-stream flow that must be left behind when
abstracting from the supply rivers. For Wilmington they are **structurally mismatched to the site**,
and that is the honest finding rather than a gap to be papered over:

- The refill model's supply rivers for this site are the Little Miami mainstem gages. **The City
  does not abstract from the Little Miami mainstem.** It draws contracted storage from Caesar Creek
  Lake (Thread A). A passby minimum on a river the City does not withdraw from constrains nothing.
- The real Thread A constraint is a **contracted storage volume**, which the refill model has no
  slot for.
- Setting a *plausible-looking* passby here would make a structurally inapplicable model produce a
  confident number. Per the standing discipline: **let it stay `[open]` and ask for the source.**

To close them properly, one of two things must land: (a) an Ohio EPA anti-degradation /
scenic-river in-stream minimum for the Little Miami reach `[open]`, or (b) a decision to model
Wilmington's supply as a reservoir allocation rather than as river refill — which is a modeling
change, not a data pull, and is out of scope for #1472.

### 3.3 — Where the Todd Fork statistic *does* live

Not in the profile — see §3.1, and that has not changed. But since **#886** it is no longer only a
manual characterization: the **outfall-reach** value is **committed as a screening denominator**.

`data/reference/hydrology/low-flow-7q10.yaml` now carries a `lytle creek` entry —
**0.0068 cfs, `source: derived`, `confidence: low`** — admitted under a narrow exception that
issue added to that file's header, for the case where a fact sheet has been read end to end and
**demonstrably states no design low flow at all** (§2.7 item 1). The vintage objection #1472
deferred on is answered by **disclosure rather than omission**: the citation names the 1952–1974
record period, so no reader can mistake it for a current statistic, and `confidence: low` is
carried for exactly that reason. The alternative was not derived-vs-cited, it was
derived-vs-nothing — and on this reach "nothing" renders as *unscreened*, which reads as an
absence of risk on the most effluent-dominated reach in the network.

What that turned on:

- `hydrology_balance(site=wilmington)` now returns a real check instead of "no cited 7Q10" —
  `Lytle Creek 7Q10 0.0068 cfs vs discharge 4.64 cfs -> 0.0015:1 chronic dilution (violation);
  acute 1Q10 0.0045 cfs -> 0.00097:1 (violation)`.
- `hydrology_scenario(site=wilmington)` runs too, and puts the campus on the same scale: the
  buildout's **2.30 cfs** net consumptive basin loss is **338.6×** this 7Q10.
- The WWTP's design flow moved from a regex over watch-items prose to a structured, fact-sheet-cited
  `design_flow_mgd` in `data/reference/hydrology/wilmington/routing.yaml` — a number that is now the
  numerator of a real finding should not be parsed out of a sentence.

**Still not wired, deliberately:** Todd Fork itself. `mainstem-gages.yaml` is unchanged, `03244000`
stays out of it, and Todd Fork dischargers other than Wilmington remain `no_7q10`. The committed
key is the **9.0 mi² outfall reach**, not the 219 mi² gage, and the two are a factor of 24 apart.

---

## 4. The campus — where the two threads meet

The AWS Cosler Farm campus is the **only** object that touches both threads, and it does so in
series: it **draws** from Thread A (the municipal potable system, ultimately Caesar Creek Lake) and
**sewers** to Thread B (the WWTP, ultimately Lytle Creek).

- **Disclosed cooling-water consumption: ~6M gal/yr**, direct evaporative, ~11 days/yr water-cooled.
  `[reported — Clinton County Port Authority / City Data Center FAQs]` The ~16,400 GPD average is
  arithmetic from that annual figure (6M ÷ 365).
- **The water-reservation MGD is the number that matters, and it is `[open]`.** AWS pays a
  **water-reservation fee** sized to a maximum-plausible-day figure that has **not been disclosed**.
  `[reported]` The reservation — not the consumption — is what the City must hold in contracted
  storage and treatment capacity against a peak day.
- **Do not substitute one for the other.** ~6M gal/yr is an *annual consumption* figure. A
  reservation is a *peak-day* commitment. They differ by whatever the peak-to-average ratio is, and
  that ratio is unknown. No figure is carried here in its place.
- AWS funds a **2.5-mi water main** and a **1-MG water tower**; the disclosed site-selection driver
  was **proximity to the WWTP**. `[reported]` Whether that proximity implies a **reclaimed-water**
  arrangement (campus cooling drawing WWTP effluent rather than potable) is **`[open]`** and would
  materially rewire both threads if true — it is not asserted here in either direction.
- Ardent/TAC: nothing disclosed on water. `[open]`

**The instrument to pull:** the **water-service agreement** between AWS and the City (and/or the
Clinton County Port Authority) is where the reservation MGD lives. A public-records request to the
City is the route. Until it lands this stays `[open]` — never an invented figure.

---

## 5. Standing open items

| # | item | thread |
|---|---|---|
| 1 | AWS **water-reservation MGD** — PRR to the City for the water-service agreement | A + B |
| 2 | Whether campus cooling uses **reclaimed WWTP effluent** rather than potable | A + B |
| 3 | **1970 USACE ↔ ODNR contract text** (primary instrument; 12.7% is secondary-sourced) | A |
| 4 | The **"up to 7 MGD" purchase ceiling** — unsupported by any pulled instrument | A |
| 5 | ODNR → City **reimbursement schedule** | A |
| 6 | Ohio EPA **anti-degradation / scenic-river in-stream minimum** → the `passby_*` knobs | B |
| 7 | Koltun **regional DAR exponent `b`** for Ohio low flows (not load-bearing here — §2.5) | B |
| 8 | ECHO **DMR/SNC history** for OH0028134 — actual discharged flow vs the 3.0/4.5 MGD design | B |
| 9 | ~~Whether Todd Fork should enter the **committed basin screen**~~ — **RESOLVED (#886)**, but narrowly: the **outfall reach** (`lytle creek`, 0.0068 cfs) is committed as a `source: derived` denominator with the record period disclosed (§3.3). Todd Fork itself is still out, and its dischargers other than Wilmington stay `no_7q10` | B |
| 10 | The **summer 30Q10** for this reach. The committed entry carries the *annual* 30Q10 only, so the seasonal-pinch screen does not run for Wilmington — a season-specific LP3 on the 1952–74 record would produce one, and nobody has computed it | B |

---

## Sources

**Primary — pulled 2026-08-01**

- USGS NWIS site service (expanded + series catalog): `03243150`, `03244000`, `03240000`,
  `03245500`, `03242350` — station metadata, published drainage areas, record inventories
- USGS NLDI (NHDPlus) — point snapping, downstream navigation, upstream-basin polygons for comids
  3932402 / 3932432 / 3932414 / 3932452 / 3935784; areas computed on the WGS84 ellipsoid
- USGS NWIS daily values, `03244000` 1952–1974 → LP3 via
  `watermark.hydrology.lowflow_frequency.compute_low_flow_frequency`
- Ohio EPA NPDES fact sheet **1PD00013.fs** (2023-05-19) — `data/documents/oepa/wilmington/1PD00013.fs.pdf`,
  extraction at `data/extracted/oepa/wilmington/1PD00013.fs.npdes.yaml`

**Secondary**

- City of Wilmington, "About Water Treatment" — <https://wilmingtonohio.gov/about-water-treatment/>
- Marzulla Law, "Render unto the Corps What is Due for the Caesar Creek Project" (the 1970
  contract, the 12.7% term, the CFC decision) — <https://marzulla.com/blog/render-unto-the-corps-what-is-due-for-the-caesar-creek-project/>
- Ohio's Country Journal, "Ohio suing Army Corps of Engineers related to overcharges at Caesar
  Creek Lake", 2020-03-16 — <https://ocj.com/2020/03/ohio-suing-army-corps-of-engineers-related-to-overcharges-at-caesar-creek-lake/>
- Clinton County Port Authority / City of Wilmington Data Center FAQs —
  <https://www.chooseclintoncountyoh.org/news/data-center-faqs> ·
  <https://wilmingtonohio.gov/data-center-faqs/>

**In-repo**

- `data/reference/hydrology/low-flow-7q10.yaml` — the committed `lytle creek` screening
  denominator (#886, §3.3) and the verified-negative exception in its header
- `data/reference/hydrology/wilmington/routing.yaml` — the structured, fact-sheet-cited
  `design_flow_mgd` the balance reads as the discharge numerator
- `data/reference/hydrology/mainstem-gages.yaml` — curated basin gage table
- `data/reference/hydrology/low-flow-7q10.derived.yaml` — derived LP3 7Q10s (Todd Fork
  deliberately absent; §3.3)
- `data/extracted/wilmington/data-centers.md` — the superseding register (§1.3 water hook)
- `src/watermark/sites/_profiles.py` — the `wilmington` `SiteProfile`
