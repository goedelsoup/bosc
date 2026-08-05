# Ohio Tax Credit Authority — meeting minutes

**Collection:** `odd/tca/` · source records, public meeting minutes

Ohio Tax Credit Authority (TCA) meeting minutes. The TCA is a state board that approves
Job Creation Tax Credit (JCTC) and Job Retention Tax Credit (JRTC) agreements administered
by the Ohio Department of Development. Minutes are public record; as-received filenames
preserved.

## Documents

| File | Date | Notes |
|---|---|---|
| `Meeting_Minutes_1.27.25.pdf` | January 27, 2025 | Anduril / Arsenal-1 (Pickaway Co.) 30-yr JCTC, 4,008 jobs |
| `Meeting_Minutes_6.2.2025.pdf` | June 2, 2025 | ark data centers JCTC terminated (no credits issued); Cologix + Lambada |
| `Meeting_Minutes_TCA_1.28.2026_gyzb8y.pdf` | January 28, 2026 | Chair: Eric Lindner; Bath & Body Works restructuring; WAF set 21.286% |
| `Meeting_Minutes_TCA_3.30.2026.pdf` | March 30, 2026 | Vantage Data Centers OH21 grantees added; Vertiv Ironton + Westerville extension |
| `TCA_Meeting_Minutes_6.1.2026.pdf` | June 1, 2026 | **Cologix data center tax exemption, 50% / 10 yrs** — the last one granted |
| `Meeting_Minutes_TCA_6.29.2026.pdf` | June 29, 2026 | First meeting wholly under the pause: 7 projects, **zero** data-center exemptions |

## Data center relevance

- **June 2025:** `ark data centers, LLC` — JCTC terminated with company's written consent,
  no credits were ever issued. County of record not specified in the minutes.
- **June 2025:** `Cologix, Inc.` — added `Lambada, Inc.` as a co-grantee on an existing
  Franklin County JCTC (Cologix is already in the ODD tax incentives CSV with a Datacenter
  Tax Exemption).
- **March 2026:** `Vantage Data Centers Management Company, LLC` — added two Ohio LLCs
  as grantees: `Vantage Data Centers OH21, LLC` and `Lancaster Newark Road OH 21, LLC`
  (both FEIN 85-1505619). "Lancaster Newark Road" locates a facility in the Fairfield/
  Licking County corridor east of Columbus.
- **March 2026:** `Vertiv Corporation` — new 10-year JCTC in Ironton (Lawrence County),
  520 new jobs, $26M new payroll; plus extension of existing Westerville facility credit
  to 12 years.
- **June 1, 2026:** `Cologix, Inc` — a **Datacenter Tax Exemption of 50 percent for 10 years**
  for Orange Township (Delaware County) and the City of Johnstown (Licking County), against 90
  FTEs / $10,000,000 new annual payroll and $5,185,126 retained; term 2026-01-01 → 2035-12-31;
  vote 3-0, Garczyk and Kelly abstaining (p. 2). This is **five days after** the Governor's
  2026-05-27 direction to pause consideration of *new* data-center exemption requests — the two
  are consistent only if the pause is read as written, applying to new requests.
- **June 29, 2026:** the first meeting **wholly under the pause** — seven new JCTC projects and
  **no data-center exemption at all**. A Van Wert item appears and is **not** a data center:
  "Van Wert Forward II" under Transformational Mixed-Use Development, for which the Authority
  engaged the University of Cincinnati Economics Center as third-party analyst. The committed ODD
  export carries the same name as an Ohio Historic Preservation Tax Credit approved 2022-06-22.

## The Van Wert / QTS negative (#1407)

**No application, award or agenda item naming Van Wert, QTS, QTS Realty Trust Inc. or QTS Van Wert
LLC appears in the four 2026 minutes read** — 2026-03-30, 2026-06-01 and 2026-06-29 from this
collection, plus **2026-04-27**, which was read from the DAM and *not* committed because it carries
no data-center item of any kind; it is cited there by URL and read date. That is the state half of the incentive
negative recorded in
[`data/extracted/van-wert/incentive-water-instruments.yaml`](../../../extracted/van-wert/incentive-water-instruments.yaml).
The 2026-07-27 minutes are not yet published — the Authority approves minutes at the *following*
meeting, so each set appears about a month in arrears.

## Route

These PDFs live on the **Ohio DAM** (`dam.assets.ohio.gov`), the same open, unauthenticated,
scriptable route as the Ohio EPA permit DAM — but under **two alternating filename patterns**, and
which one a given meeting uses is not predictable:

```text
.../development.ohio.gov/business/stateincentives/TCA_Meeting_Minutes_<M.D.YYYY>.pdf
.../development.ohio.gov/about/taxcreditminutes/Meeting_Minutes_TCA_<M.D.YYYY>.pdf
```

Probe both. The `development.ohio.gov` tax-credit-authority page itself is JS-rendered and its
HTML carries no DAM links.
