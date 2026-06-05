# Written Testimony — Ohio Select Committee on Data Centers

**Beneficial-Ownership Disclosure in Ohio Data Center Development**
**Witness:** Cory Parent — Allen County resident & cloud infrastructure engineer (interested party)
**Dated:** June 1, 2026 · **Delivered orally:** 2026-06-04 (see [oral index](bosc-committee-testimony-2026-06-04.index.yaml))
**Source:** [bosc-written-testimony-2026-06-01.pdf](../../documents/legal/bosc-written-testimony-2026-06-01.pdf) (8 pp.)

> Faithful reproduction of the submitted text (the PDF carries a text layer). To
> Co-Chairs **Holmes and Chavez** and members of the Select Committee on Data Centers.

---

Good afternoon, Co-Chairs Holmes and Chavez, and members of the Select Committee on Data
Centers. My name is Cory Parent. I am a resident of Allen County and a software and platform
engineer who builds and operates cloud infrastructure for regulated industries — healthcare,
financial services, and commercial real estate. I work daily with the platforms these facilities are
built to serve and with the economics that govern how their capacity is bought, sold, and consumed.

I am here to make one argument, and to make it plainly: **Ohio extends substantial public benefits
to data center developers without requiring them to disclose who they are.** That gap should be
closed. I am not opposed to data centers — Ohio should welcome them, and the bills already before
this Committee get a great deal right. But every other safeguard the State is building depends on a
question Ohio law does not currently make anyone answer: **who is the customer?**

## The Gap: Ohio Subsidizes Developers It Cannot Name

Ohio grants tax abatements through the Department of Development, commits public water and power,
and in some cases finances infrastructure — for entities that need never disclose their ultimate
ownership to the public bodies extending those benefits. A shell company can hold the deed, sign the
development agreement, and receive the abatement while the principal behind it stays hidden from the
community paying for it.

I can speak to this directly. In American Township, in my county, a data center representing roughly
**half a billion dollars** in capital investment was negotiated for about **fifteen months under a
non-disclosure agreement with a Delaware shell company** formed for the purpose. The developer's
identity was withheld from the public the entire time, and **key engineering specifications were
redacted from a public environmental permit as proprietary.** The local officials who approved
abatements and committed water did so in good faith, on incomplete information, because nothing in
Ohio law required more. This is not a criticism of those officials. It is a description of a gap in the
law — and it is fixable. [1]

## A Common Definition the Whole Code Can Use

Before the State can disclose who is behind a facility, it has to agree on what the facility is. The only
definition of "computer data center" in the Revised Code lives in the tax-exemption statute
(R.C. 122.175(A)(2)) — written to administer that one program, tied to capital-investment and
payroll minimums. [2] It is circular and program-bound: it says nothing about size, load, or function,
and was never meant to govern zoning, water allocation, utility service, or environmental permitting.
The proposed constitutional amendment shows the alternative instinct — it defines a data center by a
**measurable threshold, an aggregate or peak load above twenty-five megawatts.** [3] Ohio should
adopt one standard definition — **capacity-based, technology-neutral, and able to aggregate facilities
under common ownership** — and use it across the Revised Code, so the abatement statute, the utility
tariff, the water-reporting rule, and any size threshold all govern the same thing. Without it, every
safeguard rests on a term each agency reads differently and a developer can structure around.

## Why Disclosure Is the Foundational Fix

Nearly every other protection the State is pursuing quietly depends on disclosure. The cost-causation
principle in the PUCO's data center tariff and in **House Bill 706** depends on knowing who the
cost-causer is. The anti-speculation forecasting the **Ohio Consumers' Counsel** urged depends on
verifying who stands behind a load request — and **PJM's** own load-forecasting reform now requires
NDAs that at least permit sharing a load's identity with the grid operator: an explicit acknowledgment
that disclosure and reliability travel together. The **25-megawatt threshold** in the proposed
amendment cannot aggregate parcels to a common owner precisely because no disclosure requirement
exists; hyperscale infrastructure is distributed by design and routes around a per-parcel ceiling as
routine site planning. [4] And public trust erodes when a community cannot find out who it is being
asked to subsidize — the petition's own organizers used the words **"cloaked in secrecy."** [5]
Disclosure does not compete with these concerns; it is the common foundation underneath all of them.

## What Ownership Hides: The Government-Cloud Premium

There is an economic dimension to ownership the public record cannot see, sharpest in a state with
Ohio's defense footprint. Government cloud ("GovCloud") environments that host federal and defense
workloads are not a labeling difference — they are a different cost structure and addressable market.
Government cloud capacity runs **roughly 20–30% above commercial rates** because of physical
isolation, U.S.-persons staffing, and compliance overhead. [6]

What drives the premium is the **authorization level**, which also dictates the physical facility.
FedRAMP governs federal cloud work; the DoD impact levels form a ladder above it — **IL4/IL5**
for sensitive/national-security data, **IL6** for classified up to SECRET. At the higher levels the rules
require dedicated, physically isolated infrastructure and vetted U.S.-persons staffing; a facility built
for IL5/IL6 is, by regulation, **not** the flexible shared capacity a commercial abatement forecast
assumes. [7] This is not abstract in Ohio: the state hosts **Wright-Patterson Air Force Base** and an
extensive defense supplier network, making high-authorization hosting a realistic end use here. [8] A
facility serving that demand has a different margin, customer, and a far more durable revenue base —
and when the State scores an abatement on commercial assumptions, the public may be underwriting a
more valuable, more permanent enterprise than the one it was shown.

The authorization posture also governs **who in Ohio may do business with the facility at all.** A
high-authorization enclave's capacity is not sold to the open market; an IL5/IL6 environment cannot
host a local hospital, a regional bank, or a county government as a tenant, because the isolation is the
whole point. So a facility presented as shared digital infrastructure may, depending on end use, be
capacity the community is **structurally barred from using** — built on local land, drawing local
water and power, and closed to local enterprise. It also determines whether the facility **seeds a local
technology cluster or remains a sealed island**: a government enclave's supply chain is federal and
out-of-region, its workforce constrained by clearance, its capacity closed to local ventures. The
difference is a function of end use and ownership — exactly the facts disclosure would put on record.

The stakes are concrete in a two-state contrast. Ohio exempts data-center equipment from sales tax
and levies no tangible personal property tax, and abates real-property improvements 75% for 15–30
years. Of **thirteen data-center agreements approved through September 2024 (~$5.1B investment):
356 jobs, $31.6M annual payroll, against ~$281.9M state revenue loss** — closer to **$1M per job**
with local sales-tax losses included. [9] Virginia taxes data-center equipment as business personal
property: **Loudoun County draws ~38% of its general-fund revenue from data centers** on ~4% of
its commercial parcels (>$100M/yr), and has cut its residential property-tax rate every year for a
decade. The same capital can fund schools and lower homeowner taxes, or occupy land and draw
power while contributing almost nothing for a generation. The instrument that closes the gap is a
**community benefits agreement** — and to date **none has been negotiated for any Ohio data center**,
because NDA-governed negotiations present a community with terms already finalized. [10]

## A Technical Caution on the Sales-Tax Exemption Forecast

The Data Center Tax Exemption is scored against a forecast of what the facility will buy. [11] That
forecast is harder than it looks: the equipment does not sit still. Hyperscale facilities refresh servers
on a **3–5 year cycle**, and at AI-class densities per-rack hardware cost has risen **an order of
magnitude.** [12] The exempted purchases are a **recurring, escalating stream**, not a one-time
build-out; a forecast built on initial fit-out or conventional unit costs will **understate the realized
exemption substantially**, and the gap compounds each refresh. The State should build refresh cycles
and current unit costs into the forecast rather than scoring a single snapshot.

## Where the Current Bills Get It Right — and Where They Stop Short

**House Bill 706** (Reps. Thomas and Rader) is the strongest vehicle: it makes cost causation
enforceable (long-term service agreements, minimum billing demand, exit fees, a bar on shifting
data-center costs onto other ratepayers) and extends statewide a PUCO-confirmed tariff. [13]
**House Bill 646**'s study commission is the right venue for questions that need study; the **Electricity
Forecast Integrity Act** addresses speculation. These efforts are not insufficient — they are
**incomplete without disclosure**, and disclosure makes each work better.

On **HB 646**: a study commission is only as good as the information it is fed. The parties with the
most knowledge are the operators, who have every incentive to shape its conclusions; without an
independent source of facility-level data, a commission is **vulnerable to capture**. On **HB 706**:
keep its requirements anchored in retail service terms and align interconnection provisions with
**FERC's** PJM framework (Federal Power Act = FERC over wholesale cost creation; states over retail
allocation) so it holds up if challenged.

## Recommendations

1. **Condition any public incentive, abatement, or infrastructure commitment on disclosure of the
   developer's beneficial owner and controlling parent** into the public record (cf. the federal
   Corporate Transparency Act framework and Ohio procurement). The foundational fix. [14]
2. **Advance HB 706** as the core consumer-protection vehicle, anchored in retail service terms and
   aligned with FERC's framework.
3. **Use HB 646's study commission** to close the water-visibility gap Director Mertz identified —
   require data centers on public water systems to **meter and report facility-level use** — and
   recommend a load standard based on **local grid headroom** rather than a flat megawatt figure.
4. **Require publicly accessible, near-real-time facility-level reporting** of resource use (WUE/PUE)
   and disclosure of the facility's **federal authorization posture** (any FedRAMP authorization or
   DoD impact-level accreditation, and any government-related equipment/capacity hosted on site).
   The data already exists in operators' systems; what is missing is the requirement to publish per
   facility rather than rolled into a corporate aggregate.
5. **Build on the forecasting and anti-speculation work** already underway, so investment rests on
   demonstrated need and existing consumers are protected from stranded costs.
6. **Treat each abatement as a negotiation, not a concession** — with ownership and end use in hand,
   condition incentives on enforceable community benefits (permanent employment, resource use,
   local investment) of the kind no Ohio data-center agreement has yet secured.

## Disclosure and Standing

The witness filed written comment in his community's local zoning process before these circumstances
became publicly known, establishing a good-faith record as a process participant. He discloses a
**recently incorporated govtech startup** whose thesis is offering transparency and making enabling
it a core design principle. The recommendations rest on structural facts that are a matter of public
record, not on disclaiming that interest.

> "Ohio can welcome this industry and protect the communities that host it. The framework is most of
> the way built. Requiring developers to disclose who they are completes it."

---

## Sources (14 footnotes, as submitted)

1. **Ohio data center NDA secrecy / local-official disclosure** — Reps. Brian Stewart & Adam Bird introduced **HB 695** to prohibit certain local officials from signing economic-development NDAs. *Ohio Society of CPAs / Ohio Capital Journal, Mar 2026.*
2. **Statutory definition** — only definition of "computer data center" is **R.C. 122.175(A)(2)** (+ minimums at (A)(5)); program-specific, no size/load/function threshold. *ORC; OAC 122:28-1-01.*
3. **Capacity-based definition** — Ohio Prohibition of Construction of a Data Center Amendment (2026), proposed **§36a, Art. II**: aggregate monthly demand or peak load **> 25 MW.** *Ballotpedia; Ohio Capital Journal, Apr 2026.*
4. **Aggregation gap** — amendment sets 25 MW ceiling but no ownership-disclosure/parcel-aggregation; certified by Ohio Ballot Board (~413,000 signatures by Jul 1, 2026). *Ballotpedia; OCJ 2026.*
5. **"Cloaked in secrecy"** — ballot organizers/rural residents on NDA secrecy. *Ohio Capital Journal; Cincinnati Enquirer, 2026.*
6. **GovCloud premium** — AWS GovCloud ~20–30% above commercial (m5.large GovCloud US-East = 26% premium); BCG documents up to 30% for sovereign cloud (isolation, U.S.-persons, CLOUD Act). *ProsperOps 2024; CapLinked 2026; BCG "Cloud Cover" Aug 2025.*
7. **FedRAMP/DoD impact levels** — DoD CC SRG extends FedRAMP: IL4 (CUI), IL5 (higher CUI + NSS) need dedicated infra + U.S.-citizen staff; **IL6** = classified up to SECRET, wholly dedicated, SIPRNet. *DoD CC SRG.*
8. **Ohio defense footprint** — Wright-Patterson AFB + supplier network; **Google Distributed Cloud air-gapped appliance holds DoD IL5**, MIL-STD-810H; **Air Force Rapid Sustainment Office** a named early customer; GDIT + Google Public Sector demoed at **Exercise Mobility Guardian 2025**. *Google Cloud blog; Breaking Defense; Defense One; GDIT, 2024–25.*
9. **Ohio subsidy scale** — Dept. of Development: 13 agreements through Sep 2024 (~$5.1B) → 356 jobs, $31.6M payroll vs ~$281.9M revenue loss (>$343M w/ local sales tax). Microsoft 2024: 90.9% of investment, 4.8% of new FTE jobs. *Policy Matters Ohio Jan 2025; News 5 Cleveland 2026.*
10. **Virginia / Loudoun** — taxes equipment as business personal property; ~38% of general fund from data centers on ~4% of commercial parcels (>$100M/yr); residential rate cut $1.145 (2016) → $0.805/$100 (2025). No Ohio CBA yet. *Loudoun County; Policy Matters Ohio; WOUB, 2025–26.*
11. **Sales-and-use tax exemption** — **R.C. 122.175** (min $100M capital / 3 yrs, ≥$1.5M payroll), Tax Credit Authority; ~$554.9M in exemptions in 2024; no TPP tax. *ORC; Tax Foundation; PMO; News 5, 2025–26.*
12. **Refresh cycles / AI rack costs** — 3–5 yr refresh (3-yr TCO horizon for AI); traditional racks ~5–15 kW vs AI 40–120+ kW; GPU servers ~$200k–$450k (H100) to >$500k (B200). *McKinsey; Dell'Oro; CHG-Meridian, 2025–26.*
13. **HB 706 (Thomas & Rader)** — long-term service agreements, minimum billing demand, exit fees/collateral, bar on cost-shifting; extends the AEP Ohio tariff statewide. *Ohio House; Statehouse News Bureau, Feb–Mar 2026.*
14. **Federal beneficial-ownership framework** — Corporate Transparency Act (FinCEN); Mar 2025 interim final rule narrowed reporting to foreign-formed entities, exempting U.S.-formed. Concept remains established; State may require it as an incentive condition. *FinCEN; Treasury, 2025.*
