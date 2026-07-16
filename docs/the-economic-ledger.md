# The economic ledger — what the deal costs, modeled where the record is silent

> A `#233` extension narrative, and the most quantitative one. Like
> [end-use-and-workloads.md](end-use-and-workloads.md) and
> [the-load-and-the-grid.md](the-load-and-the-grid.md) it is hand-assembled analysis
> over cited records. Every figure carries its register: `[verified]` (read from a
> cited record), `[inference: computed]` (a labeled calculation from stated constants),
> `[assumption]` (a parameter the corpus doesn't fix), `[open]` (a number the record
> withholds). One discipline governs this page:
> **where a load-bearing figure is withheld or non-binding, it is neither blanked nor guessed at a single value — it is modeled as a _band across explicit scenarios_, every constant on the table.**
> A band you can audit beats a point estimate you can't, and beats a blank. The
> defense/GovCloud case appears here as one scenario _profile_, not a finding.

The plainest way to say what this report is: the public side of this deal can be added
up, but four of the numbers that decide whether it was a good one are not in the record.
The public extended a 15-year, 75% property-tax abatement, **$14.2M** of roadwork, and —
if the campus takes it — a sales-tax exemption, to a **~$500M** build, for **~50 jobs**.
What we don't know is the building share of that $500M, the real job count, the
school-compensation terms, and the equipment spend — and each of those swings the ledger
by tens of millions. So this page does what the abatement-per-job model already does for
one figure, across the whole ledger: it states what the record fixes, names what the
record won't say, and computes the rest as a range rather than pretending to a number it
doesn't have.

———

## what the record fixes

Start with the hard columns — the terms the county's own production carries, read
straight off the records `[verified: data/extracted/legal/prr-mandamus, CRA Res #548-25]`:

| Term | Value | Register |
|---|---|---|
| CRA real-property abatement | **75% / 15 years** | `[verified]` (Res #548-25) |
| Capital investment (stated) | **~$500M** | `[verified]` (CRA §2 good-faith estimate — _not_ a cap) |
| Jobs / payroll committed | **~50 jobs / ~$4M payroll** by 2030 | `[verified]` (non-binding) |
| Roadwork, publicly routed | **$14.2M** via the Port Authority | `[verified]` |
| Company Contribution | **$14.5M** up front | `[verified]` (RDA §3.2(a)) |
| Abated tax base | **Elida Local School District** | `[verified]` |

Those are real and fixed. Note already what they do _not_ settle: the $500M is a
good-faith estimate, not a ceiling; the ~50 jobs is an estimate the agreement itself
says "may differ significantly"; and the abatement is on _real property_ only —
equipment is personal property and falls outside it. Each of those caveats is a place
the ledger turns on a number the record doesn't give.

———

## the four numbers the record won't say

The whole assessment hinges on four withheld or non-binding inputs. Naming them is half
the discipline:

1. **The building share of the $500M.** The abatement covers real property — the shell,
   the pad, the substation civil works — not the servers and electrical gear, which are
   personal property `[verified: CRA real_property_only]`. So the _abated base_ is the
   building's share of the build, and that share is **not stated** `[open]`. A
   conventional shell is a larger share; an AI/GPU-dense facility is mostly equipment, a
   smaller share.
2. **The steady-state job count.** ~50 is the CRA's own estimate, explicitly non-binding
   `[verified]`; data centers staff lean once built, so the real figure could be lower
   `[open]`.
3. **The School District Compensation Agreement.** What Elida's schools actually receive
   in lieu of the abated tax is governed by an agreement the county holds **non-public**
   `[open]` — the single most important number for whether the schools come out whole.
4. **The equipment spend, and whether the campus takes the sales-tax exemption.** Ohio's
   data-center sales-tax exemption (DCTE) is real; whether it applies to _this_ campus,
   and on how much hardware, is **not in the record** `[open]`.

Everything below is built on these four knobs. None of them is invented; each is turned
across a labeled range.

———

## modeling the abatement

The abatement is the figure the corpus already models, and the arithmetic is fully
auditable. The forgone tax over the term is:

> capex **× building share** × 0.35 assessment ratio × ~0.063 effective mills × 75% × 15 years

The assessment ratio is Ohio's statutory **0.35** `[verified]`;
the **~63 effective mills** is an `[assumption]` — the exact Elida/American-Township
commercial rate isn't in the corpus — and 75%/15-yr are `[verified]`. The only free
variable is the building
share, so it is turned across four profiles `[inference: computed]`:

| Profile | Building share | Jobs | 15-yr abatement | Per job |
|---|--:|--:|--:|--:|
| Take the application at its word | 35% | 50 | **~$43M** | ~$0.9M |
| AI / GPU-dense (equipment-heavy) | 25% | 50 | **~$31M** | ~$0.6M |
| Hyperscale-realistic (lean ops) | 35% | 30 | **~$43M** | ~$1.4M |
| GovCloud / defense-hardened | 50% | 30 | **~$62M** | ~$2.1M |

So the property-tax abatement alone runs **~$31M–$62M** forgone over fifteen years
`[inference: computed]`, with the take-the-application-at-its-word case at **~$43M**. The
public is not left with nothing — it still collects the **25% that isn't abated**, about
**~$14.5M** over the term in the central case `[inference: computed]`. The
**GovCloud/defense-hardened profile sits at the top of the band** because hardened
construction lifts the real-property share and cleared operations run lean — but it is a
_what-if_ on two knobs, **not** a claim the facility is defense (that thread stays `[open]`;
see [defense-nexus.md](defense-nexus.md)).

That the building share is a _band_, not a number, is itself corroborated by the
industry. Independent capex breakdowns put the building _shell_ at only **~15–21%** of a
data-center build, rising toward the abated base once affixed mechanical and electrical
fixtures count as real property `[reference: datacenter-industry priors]`. And Ohio draws
the line in statute — the CRA abates real property, while the sales-tax exemption (DCTE)
covers the equipment _and_ the construction materials (R.C. 122.175) — so the split the
abatement turns on is genuinely fuzzy, which is the case for modeling it across a range
rather than asserting one figure.

———

## the second subsidy, the one no one scores

The abatement is bounded and visible. The sales-tax exemption is neither. The same
building-share lever that sets the abatement sets its _inverse_: whatever share of the
$500M is **not** building is equipment, and equipment is what the DCTE exempts. _If_ the
campus takes the exemption — application `[open]` — the screening value of forgone sales
tax on the initial buildout, at Allen County's ~7.25% combined rate, is
`[inference: computed]`:

| Building share | Equipment | Exempted (initial buildout) |
|---|--:|--:|
| 35% | ~$325M | **~$24M** |
| 50% | ~$250M | **~$18M** |
| 65% | ~$175M | **~$13M** |

On the initial purchase that is on the order of _half_ the property-tax abatement. But
hardware is the part that doesn't sit still: AI-class racks turn over on a short cycle
(the relator's appendix cites ~30–40% of cost replaced annually, GPU servers at
$200k–$515k each) `[verified: data appendix]`, so across the 15-year window a single
refresh roughly **doubles** the exempted total — into the **~$25M–$47M** range, where it
can _approach or exceed_ the abatement. The building share you can't see shifts the
subsidy between two pots; it does not shrink the total. Add the two and the public's
fifteen-year give is on the order of **~$45M–$90M**, depending entirely on four numbers
the record withholds.

That the exemption is the heavier subsidy is not a screening artifact — it is what every
jurisdiction that has actually measured it reports. Virginia's legislative audit found its
data-center sales-tax exemption cost **$1.02B in a single year — 81% of all state economic
incentive spending** `[reference: JLARC 2024]`, and Ohio's own exemption ballooned to
**~$16B**, enough that the legislature moved to suspend new grants
(HB957) `[reference: datacenter-industry priors]`. The subsidy that gets the headline is
the abatement; the one that gets the money is the exemption.

———

## what comes back

Now the return side, against a county baseline that matters. Allen County had **49,577**
covered jobs in 2023, _down_ from 50,828 in 2018; its population has fallen from 106,586
(2010) to 101,685 (2023) `[verified: BLS QCEW / Census ACS, the localized baseline]`. The
~50 promised jobs are about **0.1%** of county employment — a rounding error against a
base that is already shrinking, in a county that is **2× specialized in manufacturing**
(the sector a tank plant and a refinery anchor), not in cloud. The lean headcount is the
industry norm, not a Lima quirk: automated hyperscale campuses run **~20–40 operators per
100 MW** `[reference: datacenter-industry priors]`, and Good Jobs First puts the average
data-center megadeal at **~$2M per job** (states range $1.4M–$6.4M)
`[reference: Good Jobs First]` — a band BOSC's modeled subsidy-per-job lands inside. This
is a _typical_ data-center deal, which is precisely why the structural mismatch matters.

The payroll is **~$4M/yr**, ~$60M gross over the term `[verified-stated, non-binding]` —
but the public's _direct_ slice of that is thin: Ohio's municipal income tax reaches it
only if the campus sits in a taxing jurisdiction, and a township siting yields close to
**zero** `[open]`. The clearest public gain is the ~$14.5M of un-abated property tax;
the largest potential offset — the **School District Compensation Agreement** — is the
one the county won't disclose `[open]`. The roadwork nets out ambiguously: the $14.2M is
nominally covered by the developer's $14.5M contribution, but the
RDA's **§5.5 grant-refund** returns any surplus (contribution plus public grants, less certified cost)
to the company, and only ~$3.52M has actually been awarded so far — so the net public
roadwork exposure is itself `[open]` `[inference]`.

———

## the ledger, in a band

Set it on one sheet — a fifteen-year public ledger, every uncertain line a range, not a
point:

| | 15-year figure | Register |
|---|---|---|
| **Gives** | | |
| Property-tax abatement | ~$31M – $62M | `[inference: computed]` |
| Sales-tax exemption (if taken) | ~$13M – $47M | `[inference: computed]`, application `[open]` |
| Net roadwork exposure | ≤ $14.2M, offset by §5.5 | `[open]` |
| Grid / ratepayer + basin water | not monetized here | `[inference]` (see [the-load-and-the-grid.md](the-load-and-the-grid.md), [HYDROLOGY.md](HYDROLOGY.md)) |
| **Receives** | | |
| Un-abated property tax (25%) | ~$10M – $21M | `[inference: computed]` |
| Payroll's direct public slice | ~$0 – small | `[open]` (jurisdiction-dependent) |
| School District Compensation | withheld | `[open]` |
| Permanent jobs | ~50 (≈0.1% of county) | `[verified]`, non-binding |

Read down the columns and the structural finding the corpus already names becomes a
magnitude: the public is extending **tens of millions** in forgone tax — on the order of
**$45M–$90M** before water and grid — for roughly **fifty jobs** in a shrinking county.
That is the demand-side mirror of the hydrology finding, in dollars:
**the public subsidizes the load and the consumption, not the employment** — and it does so for a
counterparty named only as a Delaware shell.

———

## where this stops

What the model does _not_ do is hand back a verdict, because four numbers it cannot see
would move the sign. A version of this deal pencils out — a high real job count, a low
building share, the exemption never taken, a generous school-compensation agreement — and
a version is a deep net cost — fifty jobs become twenty, the exemption is taken and
refreshed, the township collects no income tax, the schools are made whole only on paper.
The record does not say which, and the four figures that would settle it — the building
share, the job count, the equipment spend, the school-compensation terms — are withheld,
non-binding, or simply absent.

That is the honest end, and it is an argument for the band rather than against it. The
abatement-per-job model carries the same `[open]` for the same reason `[verified:
cra-agreement.cra.yaml amounts_public: false]`. A point estimate here would be false
precision; a blank would understate a public commitment that is plainly large. The band
is the truthful object: it says the public give is tens of millions against fifty jobs,
it shows exactly which withheld numbers would narrow it, and it leaves the verdict where
it belongs — waiting on a disclosure the county has so far declined to make.

———

## sources

- The abatement, capital, jobs, roadwork, and contribution terms — the county's PRR
  production (`data/extracted/legal/prr-mandamus/`), CRA No. 1 (Res #548-25), RDA §3.2(a)
  / §5.5; synthesized in [ECONOMICS.md](ECONOMICS.md) §2
- The abatement-per-job model and its labeled constants (assessment 0.35, ~63 mills,
  75%/15-yr, the four profiles) — the Cost chapter's follow-the-money model
  (`web/packages/core/src/moneyFlow.ts`, `buildAbatementPerJob`); the non-public school terms —
  `cra-agreement.cra.yaml` (`amounts_public: false`)
- The 15-year ledger figures — `[inference: computed]` from those constants (building
  share, job count, and the ~7.25% Allen County sales-tax rate turned across scenarios)
- The DCTE sales-tax exemption, the AI-rack cost curve, and the GovCloud premium — the
  relator's committee data appendix
  (`data/extracted/legal/select-committee-2026/relator-testimony/`); [ECONOMICS.md](ECONOMICS.md) §4
- The localized employment and population baseline — the BLS QCEW / Census ACS generated
  baseline (`/watershed/economics-baseline`, area 39003)
- The frames this sits beside — [the-load-and-the-grid.md](the-load-and-the-grid.md),
  [end-use-and-workloads.md](end-use-and-workloads.md), [DOSSIER.md](DOSSIER.md) §6
