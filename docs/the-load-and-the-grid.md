# The load and the grid — a city's worth of demand, and who carries it

> A `#233` extension narrative. Like [end-use-and-workloads.md](end-use-and-workloads.md)
> and [defense-nexus.md](defense-nexus.md) it is hand-assembled analysis over cited
> records, and it ends at the questions it cannot close. Every statement carries its
> register: `[verified]` (read from a cited record or a connector pull), `[inference]`
> (a labeled derivation), `[open]` (a question the record does not answer),
> `[reference]` (an outside-published figure or law). Two disciplines govern this page,
> because the two phrases people reach for are both softer than they sound. **The
> headline "313 MW" is _backup generation_, not the operating load — and the number
> behind it is redacted in the final permit.** And **"behind-the-meter" is a proponent
> _claim_, not a documented fact about this campus**, which the record classifies as a
> grid-served retail customer. What survives both disciplines is still large, and still
> the point: a single campus is a material fraction of its utility's entire load, for a
> headcount a big-box store would exceed.

The plainest way to say what this report is: the campus is a very large electricity
customer — on the order of a mid-size city's demand, on one corridor — and it is served
off the grid by AEP Ohio inside the PJM market. That much the record carries. The two
things most often said _about_ that load — its exact size, and whether it runs
"behind the meter" — are where the record gets thinner than the confidence around them,
and where the public-cost question actually lives. This walks the solid part, the soft
part, and the part that isn't in the record at all.

———

## the number everyone cites is the backup — and it's redacted

The figure in every summary is **~313 MW**. It is real, and it is worth being precise
about what it measures. It comes from the campus's Ohio EPA air permit: **114 diesel
emergency generators × ~2,750 ekW each ≈ 313 MW**
`[verified: OEPA Air PTI P0138965, draft — data/extracted/permits/3987141.epa.yaml]`.
That is **standby capacity** — the diesels that run when the grid drops — not the power
the campus pulls to do its work.

And the per-engine rating behind it does not survive into the final document. The
**final** permit, issued 2026-05-28, **redacts the engine make, model, and size as
Confidential Business Information / trade secret** (Comments 16, 19; Response 16),
confirming only the unit _count_ — 114 data-hall gensets plus one smaller HUBGEN, 115
emission units — and the emission _rates_. The **~2,750 ekW/engine figure behind the
~313 MW total comes from the _draft_ public notice, not the issued permit**
`[verified: data/extracted/permits/4132514.epa.yaml]`. So the most-quoted number about
this facility's power rests on a draft the final record withheld — the same
withholding-as-evidence pattern that runs through the rest of the corpus.

The _operating_ load is an inference, and it's labeled as one. Backup capacity on a
hyperscale design tracks IT load at roughly N+1, which puts the IT load near
**~250–300 MW** (midpoint **275**) `[inference: N+1 backup ≈ IT]`, and the total
facility draw — IT plus cooling and losses, through the power-usage model — near
**~348 MW** `[inference: IT × PUE]`. Those are the numbers the rest of this page uses,
carried as inferences, not facts. The honest version of the headline is: a standby bank
the record sizes at ~313 MW, around a working load the record lets you _estimate_ at a
city's scale but never states.

———

## a city's worth of demand on one corridor

Take the inferred ~348 MW facility draw at a realistic load factor and the annual
energy is **~2,740 GWh/yr** `[inference: derived]`. Set against the grid it sits in,
the comparison is the finding:

| Against | Annual load | Campus share | Basis |
|---|--:|--:|---|
| AEP Ohio retail sales | ~48,653 GWh | **~5.6%** | `[connector: EIA-861, 2024]` |
| Ohio retail electricity | ~161,934 GWh | ~1.7% | `[connector: EIA]` |
| PJM total load | ~815,056 GWh | ~0.34% | `[connector: EIA-930, 2024]` |

The headline reads off the first row: **a single campus equals roughly 5–6% of its
serving utility's entire retail electricity sales** `[connector]`. By a different yard-
stick, its ~2,740 GWh/yr is the consumption of **~260,000 Ohio homes**
`[inference: derived, EIA-cited]`, ~1.8% of all the electricity sold at retail in the
state. This is one customer, on one corridor, sized like a small city.

Whether the grid can _physically_ carry it is not the worry. Over a representative
summer, PJM's in-balancing-authority generation runs ~5,747 MW above its own demand on
average, so a ~348 MW load sits comfortably inside that headroom without net imports
`[connector: EIA-930, screening]`. The question a load this size raises is not _can the
power be generated_ — it can. It is _who pays for moving it_.

———

## load, not jobs

This is the comparison the public record actually substantiates. Set the verified
columns side by side `[verified: ECONOMICS.md §2, the county's own production]`:

- a **~275 MW** IT load (inferred) and **3.1–3.84 MGD** of consumptive cooling water,
  against
- **~50 permanent jobs** and **~$4M** of payroll by 2030, on a **15-year / 75%** tax
  abatement over a **~$500M** build, with **$14.2M** of roadwork routed through the
  public Port Authority.

That is on the order of **~5–6 MW per job** `[inference]` — a community-scale electrical
load and a multi-MGD basin draw, for a headcount a single big-box store would exceed.
The structural argument the corpus _substantiates_ is exactly that: **the public
subsidizes load and consumption, not employment** `[inference]` — and does so, per the
land record, for a counterparty named only as a Delaware shell. It is the demand-side
mirror of the water finding: the burden scales with the megawatts, the public benefit
scales with the jobs, and the two are orders of magnitude apart.

———

## who carries the grid

A load this size has a price the campus sees and a price the public might. The campus's
own footprint in the PJM market, sized against published price signals, is large:
roughly **$96M/yr** in energy at the AEP-zone wholesale price and roughly **$34M/yr** in
capacity at the 2025/26 auction's clearing rate — a price that **spiked ~9×** over the
prior year `[reference: PJM Data Miner / RPM, screening, verify-flagged]`. Those are the
campus's costs, not the public's. The public-cost question is the one underneath them,
and it is **`[open]`**: who pays for the _interconnection and network upgrades_ a new
community-scale load requires — the campus, or the ratepayers on the same system?

The record sets up that question without answering it. The campus is classified a
**PUCO-regulated retail customer of AEP Ohio** — grid-served, not wholesale
`[verified: FERC seam, classification]`. Its ~2,740 GWh/yr lands as ~1.8% of Ohio retail
sales, the basis for a deliberately stylized **0.9–1.8%** consumer-price-pressure screen
that the corpus flags as a _sensitivity, not a forecast_ `[inference, low]`. The
proponents say the cost-causers pay: Google testified it takes service under PUCO-
approved tariffs and runs a 100 MW PJM virtual-power-plant; a competitor witness invoked
**"BYONG" (Bring Your Own New Generation)** to "deliver more than we utilize." But the
same testimony carries **no per-site disclosure** of who operates that way, or what share
`[verified: proponent-analysis.md]`. Whether _this_ campus's grid upgrades fall on the
campus or the rate base is not in the record.

———

## the behind-the-meter question

The phrase that travels with this facility is "behind-the-meter," and it deserves the
same discipline as the megawatts. Behind-the-meter co-location — a large load wired
directly to a generator, bypassing the grid it would otherwise pay into — is a live and
unsettled federal question: FERC **rejected** the Susquehanna–Amazon co-location
amendment (`ER24-2172`, 2024-11-01) and opened a technical conference on the broader
issue (`AD24-11-000`) `[reference: FERC dockets, verify-flagged]`. It is real, and it is
exactly the kind of arrangement that would move who-pays from PUCO to FERC.

For _this_ campus, it is **`[open]`**. The record classifies the campus as grid-served
retail. The 114 generators are **emergency backup**, explicitly not primary generation
`[verified: air permit]`; whether any _primary_ on-site generation exists, and on what
fuel, is **unproven** in the corpus `[open]`. The developers' public FAQ lists
"behind-the-meter power" among its efficiency claims `[reference: AEDG]`, but a marketing
claim is not a documented interconnection. So the honest statement is the narrow one:
behind-the-meter is the policy seam this load _sits next to_, and a posture its
proponents _market_ — not an arrangement the record shows for the Lima campus.

———

## where this stops

Strip it to what the record will and won't carry. It will carry the scale: a campus that
is ~5–6% of its utility's entire retail load, ~260,000 homes of annual consumption, for
~50 jobs — load, not jobs, with confidence. It will carry the grid it sits in: AEP Ohio,
PJM, a capacity price that just spiked ninefold. What it will _not_ carry is three things
the public-cost verdict actually needs:

- **the real operating load** — the figures are nameplate and inferred, and the nameplate
  behind the famous "313 MW" is redacted in the issued permit `[open]`;
- **who bears the grid cost** — whether the interconnection and upgrades fall on the
  campus or the rate base is not disclosed `[open]`;
- **whether any of it runs behind the meter** — claimed and marketed, not documented
  `[open]`.

A megawatt is easy to print and hard to hide; that is why the load is the solid part of
this story. Who pays to carry it, and on whose meter, is the part the record keeps — and
until that is disclosed, the honest reading is the one the numbers already force: the
public is being asked to host a city's worth of demand for a small town's worth of jobs,
and to take the cost allocation on faith.

———

## sources

- The ~313 MW backup, the IT-load and facility-draw inferences, the load-vs-jobs
  mismatch, and the consumer-price-pressure screen — [ECONOMICS.md](ECONOMICS.md)
  §1, §3, §6 (hand-assembled over cited records)
- The redaction of the per-engine rating in the final permit — `data/extracted/permits/4132514.epa.yaml`
  (Comments 16, 19; Response 16); the ~2,750 ekW draft figure — `data/extracted/permits/3987141.epa.yaml`
- The serving utility, the grid shares, the PJM headroom and market footprint, and the
  FERC jurisdictional seam — `docs/GRID.md` §#94–#97 (epic #93); the datasets under
  `data/reference/eia/`, `data/reference/pjm/`, `data/reference/ferc/`
- The proponents' grid-cost and BYONG claims, and the absence of per-site disclosure —
  [legal/proponent-analysis.md](legal/proponent-analysis.md)
- The abatement, jobs, capital, and roadwork terms — the county's PRR production,
  CRA Res #548-25; [DOSSIER.md](DOSSIER.md) §6
- The water consequence of the same load — [HYDROLOGY.md](HYDROLOGY.md),
  [toxics-and-the-corridor.md](toxics-and-the-corridor.md)
